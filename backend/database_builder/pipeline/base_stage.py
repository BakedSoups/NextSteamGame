"""
Base stage interface for the modular database builder pipeline
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import logging
import time
from dataclasses import dataclass
from pathlib import Path
import json

from backend.config import PIPELINE_PATHS


@dataclass
class StageResult:
    """Result of a pipeline stage execution"""
    success: bool
    stage_name: str
    duration: float
    items_processed: int
    output_files: list[str]
    metadata: Dict[str, Any]
    error_message: Optional[str] = None


@dataclass
class StageCheckpoint:
    """Checkpoint data for stage resumption"""
    stage_name: str
    completed: bool
    last_processed_item: Optional[str] = None
    processed_count: int = 0
    timestamp: float = 0.0
    metadata: Dict[str, Any] = None


class BasePipelineStage(ABC):
    """Abstract base class for all pipeline stages"""

    def __init__(self, stage_name: str, dependencies: list[str] = None):
        self.stage_name = stage_name
        self.dependencies = dependencies or []
        self.logger = logging.getLogger(f"pipeline.{stage_name}")
        self.start_time = 0.0
        self.checkpoint_file = PIPELINE_PATHS['checkpoint_file'].parent / f"checkpoint_{stage_name}.json"

    def execute(self, skip_if_complete: bool = True) -> StageResult:
        """Execute the pipeline stage with checkpointing support"""
        self.logger.info(f"🚀 Starting stage: {self.stage_name}")
        self.start_time = time.time()

        try:
            # Check if stage is already complete
            if skip_if_complete and self._is_stage_complete():
                self.logger.info(f"✅ Stage {self.stage_name} already complete, skipping")
                return self._create_skip_result()

            # Validate dependencies
            self._validate_dependencies()

            # Load checkpoint if exists
            checkpoint = self._load_checkpoint()

            # Execute stage-specific logic
            result = self._execute_stage(checkpoint)

            # Save completion checkpoint
            if result.success:
                self._save_completion_checkpoint(result)

            return result

        except Exception as e:
            error_msg = f"Stage {self.stage_name} failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            return StageResult(
                success=False,
                stage_name=self.stage_name,
                duration=time.time() - self.start_time,
                items_processed=0,
                output_files=[],
                metadata={},
                error_message=error_msg
            )

    @abstractmethod
    def _execute_stage(self, checkpoint: Optional[StageCheckpoint]) -> StageResult:
        """Execute the stage-specific logic"""
        pass

    @abstractmethod
    def _get_expected_outputs(self) -> list[str]:
        """Return list of expected output files/paths"""
        pass

    @abstractmethod
    def _validate_stage_inputs(self) -> bool:
        """Validate that stage inputs are available"""
        pass

    def _is_stage_complete(self) -> bool:
        """Check if stage is already complete"""
        # Check if all expected outputs exist
        expected_outputs = self._get_expected_outputs()
        for output_path in expected_outputs:
            if not Path(output_path).exists():
                return False

        # Check completion checkpoint
        checkpoint = self._load_checkpoint()
        return checkpoint and checkpoint.completed

    def _validate_dependencies(self) -> None:
        """Validate that all dependencies are satisfied"""
        for dep in self.dependencies:
            dep_checkpoint_file = PIPELINE_PATHS['checkpoint_file'].parent / f"checkpoint_{dep}.json"
            if not dep_checkpoint_file.exists():
                raise ValueError(f"Dependency {dep} not satisfied - checkpoint not found")

            try:
                with open(dep_checkpoint_file, 'r') as f:
                    dep_checkpoint = json.load(f)
                if not dep_checkpoint.get('completed', False):
                    raise ValueError(f"Dependency {dep} not completed")
            except (json.JSONDecodeError, KeyError):
                raise ValueError(f"Invalid checkpoint for dependency {dep}")

    def _load_checkpoint(self) -> Optional[StageCheckpoint]:
        """Load existing checkpoint for this stage"""
        if not self.checkpoint_file.exists():
            return None

        try:
            with open(self.checkpoint_file, 'r') as f:
                data = json.load(f)

            return StageCheckpoint(
                stage_name=data['stage_name'],
                completed=data['completed'],
                last_processed_item=data.get('last_processed_item'),
                processed_count=data.get('processed_count', 0),
                timestamp=data.get('timestamp', 0.0),
                metadata=data.get('metadata', {})
            )
        except (json.JSONDecodeError, KeyError) as e:
            self.logger.warning(f"Invalid checkpoint file, starting fresh: {e}")
            return None

    def _save_checkpoint(self, checkpoint: StageCheckpoint) -> None:
        """Save checkpoint for stage resumption"""
        checkpoint.timestamp = time.time()

        # Ensure checkpoint directory exists
        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.checkpoint_file, 'w') as f:
            json.dump({
                'stage_name': checkpoint.stage_name,
                'completed': checkpoint.completed,
                'last_processed_item': checkpoint.last_processed_item,
                'processed_count': checkpoint.processed_count,
                'timestamp': checkpoint.timestamp,
                'metadata': checkpoint.metadata or {}
            }, f, indent=2)

    def _save_completion_checkpoint(self, result: StageResult) -> None:
        """Save completion checkpoint"""
        checkpoint = StageCheckpoint(
            stage_name=self.stage_name,
            completed=True,
            processed_count=result.items_processed,
            metadata=result.metadata
        )
        self._save_checkpoint(checkpoint)

    def _create_skip_result(self) -> StageResult:
        """Create result for skipped stage"""
        return StageResult(
            success=True,
            stage_name=self.stage_name,
            duration=0.0,
            items_processed=0,
            output_files=self._get_expected_outputs(),
            metadata={'skipped': True}
        )

    def reset(self) -> None:
        """Reset stage by removing checkpoint and outputs"""
        self.logger.info(f"🔄 Resetting stage: {self.stage_name}")

        # Remove checkpoint
        if self.checkpoint_file.exists():
            self.checkpoint_file.unlink()

        # Remove output files
        for output_path in self._get_expected_outputs():
            output_file = Path(output_path)
            if output_file.exists():
                output_file.unlink()
                self.logger.info(f"Removed output file: {output_path}")

    def get_status(self) -> Dict[str, Any]:
        """Get current stage status"""
        checkpoint = self._load_checkpoint()
        expected_outputs = self._get_expected_outputs()

        output_status = {}
        for output_path in expected_outputs:
            output_file = Path(output_path)
            output_status[output_path] = {
                'exists': output_file.exists(),
                'size': output_file.stat().st_size if output_file.exists() else 0
            }

        return {
            'stage_name': self.stage_name,
            'dependencies': self.dependencies,
            'completed': checkpoint.completed if checkpoint else False,
            'processed_count': checkpoint.processed_count if checkpoint else 0,
            'last_checkpoint': checkpoint.timestamp if checkpoint else None,
            'expected_outputs': expected_outputs,
            'output_status': output_status,
            'inputs_valid': self._validate_stage_inputs()
        }


class BatchProcessingMixin:
    """Mixin for stages that process items in batches"""

    def _process_in_batches(self, items: list, batch_size: int,
                          process_func, checkpoint_interval: int = 100) -> StageResult:
        """Process items in batches with checkpointing"""
        processed_count = 0
        failed_count = 0
        output_files = []

        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]

            try:
                batch_result = process_func(batch)
                processed_count += len(batch)

                if hasattr(batch_result, 'output_files'):
                    output_files.extend(batch_result.output_files)

                # Save checkpoint periodically
                if processed_count % checkpoint_interval == 0:
                    checkpoint = StageCheckpoint(
                        stage_name=self.stage_name,
                        completed=False,
                        processed_count=processed_count,
                        last_processed_item=str(batch[-1]) if batch else None,
                        metadata={'failed_count': failed_count}
                    )
                    self._save_checkpoint(checkpoint)
                    self.logger.info(f"Checkpoint saved: {processed_count} items processed")

            except Exception as e:
                failed_count += len(batch)
                self.logger.error(f"Batch processing failed: {e}")
                continue

        return StageResult(
            success=failed_count < len(items) * 0.5,  # Success if less than 50% failed
            stage_name=self.stage_name,
            duration=time.time() - self.start_time,
            items_processed=processed_count,
            output_files=output_files,
            metadata={
                'processed_count': processed_count,
                'failed_count': failed_count,
                'success_rate': (processed_count / len(items)) * 100 if items else 0
            }
        )