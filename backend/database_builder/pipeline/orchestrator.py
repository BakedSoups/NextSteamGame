"""
Enhanced Pipeline Orchestrator for modular Steam Recommender database builder
"""
import argparse
import logging
import time
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import asdict

from .data_collection_stage import DataCollectionStage
from .review_analysis_stage import ReviewAnalysisStage
from .database_creation_stage import DatabaseCreationStage
from .base_stage import StageResult

from backend.config import (
    LOGGING_CONFIG, PIPELINE_PATHS, DATABASE_CONFIG,
    validate_pipeline_config, ensure_directories
)


class PipelineOrchestrator:
    """
    Enhanced orchestrator for the modular Steam Recommender pipeline

    Features:
    - Stage-based execution with dependency management
    - Comprehensive checkpointing and recovery
    - Detailed progress reporting and cost estimation
    - Validation and error handling
    - Configurable execution modes
    """

    def __init__(self, enable_logging: bool = True):
        self.stages = self._initialize_stages()
        self.execution_log = []
        self.start_time = 0.0

        if enable_logging:
            self._setup_logging()

        self.logger = logging.getLogger(f"orchestrator")

    def _initialize_stages(self) -> Dict[str, Any]:
        """Initialize all pipeline stages"""
        return {
            'data_collection': DataCollectionStage(),
            'review_analysis': ReviewAnalysisStage(),
            'database_creation': DatabaseCreationStage()
        }

    def _setup_logging(self) -> None:
        """Setup enhanced logging for the orchestrator"""
        # Ensure log directory exists
        ensure_directories()

        # Configure logging
        logging.basicConfig(
            level=getattr(logging, LOGGING_CONFIG['level']),
            format=LOGGING_CONFIG['format'],
            handlers=[
                logging.FileHandler(LOGGING_CONFIG['log_file']),
                logging.StreamHandler()
            ]
        )

    def execute_pipeline(self, stages: Optional[List[str]] = None,
                        skip_completed: bool = True,
                        validate_inputs: bool = True) -> Dict[str, Any]:
        """
        Execute the complete pipeline or specified stages

        Args:
            stages: List of stage names to execute (None = all stages)
            skip_completed: Skip stages that are already complete
            validate_inputs: Validate inputs before execution

        Returns:
            Execution summary with results and statistics
        """
        self.logger.info("Starting Steam Recommender Pipeline Orchestrator")
        self.start_time = time.time()

        # Validate configuration
        if validate_inputs:
            self._validate_pipeline_configuration()

        # Determine stages to execute
        stages_to_run = stages or list(self.stages.keys())
        self.logger.info(f"Executing stages: {', '.join(stages_to_run)}")

        # Execute stages in order
        execution_results = {}
        for stage_name in stages_to_run:
            if stage_name not in self.stages:
                raise ValueError(f"Unknown stage: {stage_name}")

            stage = self.stages[stage_name]
            self.logger.info(f"Executing stage: {stage_name}")

            try:
                # Execute stage
                result = stage.execute(skip_if_complete=skip_completed)
                execution_results[stage_name] = result

                # Log result
                self._log_stage_result(result)

                # Stop on failure (unless configured otherwise)
                if not result.success:
                    self.logger.error(f"Stage {stage_name} failed, stopping pipeline")
                    break

            except Exception as e:
                self.logger.error(f"Unexpected error in stage {stage_name}: {e}")
                execution_results[stage_name] = StageResult(
                    success=False,
                    stage_name=stage_name,
                    duration=0.0,
                    items_processed=0,
                    output_files=[],
                    metadata={},
                    error_message=str(e)
                )
                break

        # Generate execution summary
        summary = self._generate_execution_summary(execution_results)
        self._save_execution_log(summary)

        return summary

    def execute_stage(self, stage_name: str, **kwargs) -> StageResult:
        """Execute a single stage"""
        if stage_name not in self.stages:
            raise ValueError(f"Unknown stage: {stage_name}")

        stage = self.stages[stage_name]
        return stage.execute(**kwargs)

    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get comprehensive pipeline status"""
        status = {
            'stages': {},
            'overall_completion': 0.0,
            'dependencies_satisfied': True,
            'estimated_time_remaining': None,
            'estimated_cost': None
        }

        completed_stages = 0
        total_stages = len(self.stages)

        for stage_name, stage in self.stages.items():
            stage_status = stage.get_status()
            status['stages'][stage_name] = stage_status

            if stage_status['completed']:
                completed_stages += 1

            # Check dependency satisfaction
            for dep in stage_status['dependencies']:
                if dep in status['stages']:
                    if not status['stages'][dep]['completed']:
                        status['dependencies_satisfied'] = False

        status['overall_completion'] = (completed_stages / total_stages) * 100

        # Add cost estimation for review analysis stage
        if 'review_analysis' in self.stages:
            review_stage = self.stages['review_analysis']
            if hasattr(review_stage, 'estimate_cost'):
                status['estimated_cost'] = review_stage.estimate_cost()

        return status

    def reset_pipeline(self, stages: Optional[List[str]] = None) -> None:
        """Reset specified stages or entire pipeline"""
        stages_to_reset = stages or list(self.stages.keys())

        self.logger.info(f"Resetting stages: {', '.join(stages_to_reset)}")

        for stage_name in stages_to_reset:
            if stage_name in self.stages:
                self.stages[stage_name].reset()
                self.logger.info(f"Reset stage: {stage_name}")

    def validate_pipeline(self) -> Dict[str, Any]:
        """Comprehensive pipeline validation"""
        validation_results = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'stage_validations': {}
        }

        try:
            # Validate configuration
            validate_pipeline_config()
        except Exception as e:
            validation_results['valid'] = False
            validation_results['errors'].append(f"Configuration validation failed: {e}")

        # Validate each stage
        for stage_name, stage in self.stages.items():
            stage_validation = {
                'inputs_valid': stage._validate_stage_inputs(),
                'dependencies_satisfied': self._check_stage_dependencies(stage_name),
                'outputs_exist': stage._is_stage_complete()
            }

            if not stage_validation['inputs_valid']:
                validation_results['warnings'].append(f"Stage {stage_name} inputs not valid")

            if not stage_validation['dependencies_satisfied']:
                validation_results['valid'] = False
                validation_results['errors'].append(f"Stage {stage_name} dependencies not satisfied")

            validation_results['stage_validations'][stage_name] = stage_validation

        return validation_results

    def _validate_pipeline_configuration(self) -> None:
        """Validate pipeline configuration and environment"""
        self.logger.info("Validating pipeline configuration...")

        # Validate configuration
        try:
            validate_pipeline_config()
            self.logger.info("Configuration validation passed")
        except Exception as e:
            self.logger.error(f"Configuration validation failed: {e}")
            raise

        # Ensure directories exist
        ensure_directories()

    def _check_stage_dependencies(self, stage_name: str) -> bool:
        """Check if stage dependencies are satisfied"""
        stage = self.stages[stage_name]
        for dep_name in stage.dependencies:
            if dep_name in self.stages:
                dep_stage = self.stages[dep_name]
                if not dep_stage._is_stage_complete():
                    return False
        return True

    def _log_stage_result(self, result: StageResult) -> None:
        """Log stage execution result"""
        self.execution_log.append(asdict(result))

        if result.success:
            self.logger.info(
                f"Stage {result.stage_name} completed: "
                f"{result.items_processed} items processed in {result.duration:.1f}s"
            )
        else:
            self.logger.error(
                f"Stage {result.stage_name} failed: {result.error_message}"
            )

    def _generate_execution_summary(self, results: Dict[str, StageResult]) -> Dict[str, Any]:
        """Generate comprehensive execution summary"""
        total_duration = time.time() - self.start_time
        total_items = sum(r.items_processed for r in results.values())
        successful_stages = sum(1 for r in results.values() if r.success)

        summary = {
            'execution_time': time.time(),
            'total_duration': total_duration,
            'total_items_processed': total_items,
            'stages_executed': len(results),
            'successful_stages': successful_stages,
            'overall_success': successful_stages == len(results),
            'stage_results': {name: asdict(result) for name, result in results.items()},
            'output_files': [],
            'metadata': {}
        }

        # Collect all output files
        for result in results.values():
            summary['output_files'].extend(result.output_files)

        # Add database statistics if available
        if 'database_creation' in results and results['database_creation'].success:
            db_stage = self.stages['database_creation']
            if hasattr(db_stage, 'get_database_stats'):
                summary['metadata']['database_stats'] = db_stage.get_database_stats()

        return summary

    def _save_execution_log(self, summary: Dict[str, Any]) -> None:
        """Save execution log for analysis"""
        log_file = PIPELINE_PATHS['checkpoint_file'].parent / "execution_log.json"

        with open(log_file, 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        self.logger.info(f"Execution log saved: {log_file}")

    def print_pipeline_summary(self) -> None:
        """Print comprehensive pipeline summary"""
        status = self.get_pipeline_status()

        print("\n" + "="*80)
        print("STEAM RECOMMENDER PIPELINE STATUS")
        print("="*80)

        print(f"\nOVERALL COMPLETION: {status['overall_completion']:.1f}%")
        print(f"DEPENDENCIES SATISFIED: {'Yes' if status['dependencies_satisfied'] else 'No'}")

        print(f"\nSTAGE STATUS:")
        for stage_name, stage_status in status['stages'].items():
            completion_icon = "[COMPLETE]" if stage_status['completed'] else "[PENDING]"
            print(f"   {completion_icon} {stage_name.replace('_', ' ').title()}")
            print(f"      - Processed: {stage_status['processed_count']} items")
            print(f"      - Inputs Valid: {'Yes' if stage_status['inputs_valid'] else 'No'}")

        # Cost estimation
        if status.get('estimated_cost'):
            cost_info = status['estimated_cost']
            print(f"\nESTIMATED COSTS:")
            print(f"   - Games to analyze: {cost_info['total_games']:,}")
            print(f"   - Estimated cost: ${cost_info['estimated_cost_usd']:.2f}")
            print(f"   - Cost per game: ${cost_info['cost_per_game']:.4f}")

        # Output files
        print(f"\nEXPECTED OUTPUT FILES:")
        for stage_name, stage_status in status['stages'].items():
            for output_path in stage_status['expected_outputs']:
                exists = Path(output_path).exists()
                size = Path(output_path).stat().st_size / (1024*1024) if exists else 0
                status_icon = "[EXISTS]" if exists else "[MISSING]"
                print(f"   {status_icon} {output_path} ({size:.1f} MB)")

        print("="*80)

    def show_cost_warning(self) -> bool:
        """Show cost warning and get user confirmation"""
        status = self.get_pipeline_status()
        cost_info = status.get('estimated_cost', {})

        print("\n" + "="*70)
        print("STEAM RECOMMENDER PIPELINE WARNING")
        print("="*70)
        print("This pipeline takes 3+ days to complete due to API rate limits:")
        print("   - Data collection: ~2 hours (SteamSpy + Steam API)")
        print("   - Review analysis: ~1-2 days (OpenAI API rate limited)")
        print("   - Database creation: ~30 minutes (local processing)")

        if cost_info:
            print(f"\nESTIMATED OPENAI COSTS:")
            print(f"   - Games to analyze: {cost_info.get('total_games', 0):,}")
            print(f"   - Estimated tokens: {cost_info.get('estimated_tokens', 0):,}")
            print(f"   - Estimated cost: ${cost_info.get('estimated_cost_usd', 0):.2f}")

        print(f"\nCURRENT STATUS:")
        completion = status['overall_completion']
        print(f"   - Pipeline completion: {completion:.1f}%")

        if completion > 0:
            print("   - You can resume from where you left off")

        print("="*70)

        response = input("\nDo you want to proceed? (y/n): ").strip().lower()
        return response == 'y'


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Steam Recommender Modular Pipeline Orchestrator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run complete pipeline
  python -m backend.database_builder.pipeline.orchestrator

  # Run specific stage only
  python -m backend.database_builder.pipeline.orchestrator --stage data_collection

  # Skip warning and completed stages
  python -m backend.database_builder.pipeline.orchestrator --skip-warning --force-rerun

  # Get pipeline status
  python -m backend.database_builder.pipeline.orchestrator --status

  # Reset pipeline
  python -m backend.database_builder.pipeline.orchestrator --reset
        """
    )

    parser.add_argument("--stage",
                       choices=['data_collection', 'review_analysis', 'database_creation'],
                       help="Run specific stage only")
    parser.add_argument("--skip-warning", action="store_true",
                       help="Skip the initial cost/time warning")
    parser.add_argument("--force-rerun", action="store_true",
                       help="Force rerun of completed stages")
    parser.add_argument("--status", action="store_true",
                       help="Show pipeline status and exit")
    parser.add_argument("--reset", action="store_true",
                       help="Reset pipeline (remove checkpoints and outputs)")
    parser.add_argument("--validate", action="store_true",
                       help="Validate pipeline configuration and dependencies")

    args = parser.parse_args()

    # Initialize orchestrator
    orchestrator = PipelineOrchestrator()

    try:
        # Handle status request
        if args.status:
            orchestrator.print_pipeline_summary()
            return

        # Handle reset request
        if args.reset:
            response = input("WARNING: This will reset the entire pipeline. Continue? (y/n): ")
            if response.lower().strip() == 'y':
                orchestrator.reset_pipeline()
                print("Pipeline reset complete")
            return

        # Handle validation request
        if args.validate:
            validation = orchestrator.validate_pipeline()
            if validation['valid']:
                print("Pipeline validation passed")
            else:
                print("Pipeline validation failed:")
                for error in validation['errors']:
                    print(f"   - {error}")
            return

        # Show warning unless skipped
        if not args.skip_warning:
            if not orchestrator.show_cost_warning():
                print("Pipeline cancelled by user")
                return

        # Execute pipeline
        if args.stage:
            # Single stage execution
            stages_to_run = [args.stage]
        else:
            # Full pipeline execution
            stages_to_run = None

        summary = orchestrator.execute_pipeline(
            stages=stages_to_run,
            skip_completed=not args.force_rerun
        )

        # Print final summary
        if summary['overall_success']:
            print("Pipeline completed successfully!")
            orchestrator.print_pipeline_summary()
        else:
            print("Pipeline completed with errors")
            print(f"Successful stages: {summary['successful_stages']}/{summary['stages_executed']}")

    except KeyboardInterrupt:
        print("\nPipeline interrupted by user")
    except Exception as e:
        print(f"Pipeline failed with error: {e}")
        logging.getLogger().error("Pipeline failed", exc_info=True)
        exit(1)


if __name__ == "__main__":
    main()