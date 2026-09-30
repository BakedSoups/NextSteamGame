import assert from "node:assert/strict"
import test from "node:test"
import { updatePercentWeight } from "../lib/percent-weights.ts"

test("dragging a slider preserves peer ratios and does not mutate state", () => {
  const current = { a: 40, b: 40, c: 20 }
  assert.deepEqual(updatePercentWeight(current, "a", 70), { a: 70, b: 20, c: 10 })
  assert.deepEqual(current, { a: 40, b: 40, c: 20 })
})

test("vector and signal budgets remain independent", () => {
  const current = { a: 60, b: 40, c: 55, d: 45 }
  assert.deepEqual(updatePercentWeight(current, "a", 20, ["a", "b"]), { a: 20, b: 80, c: 55, d: 45 })
})

test("zero peers and rounding ties preserve the existing allocation order", () => {
  assert.deepEqual(updatePercentWeight({ a: 100, b: 0, c: 0 }, "a", 30), { a: 30, b: 0, c: 70 })
  assert.deepEqual(updatePercentWeight({ a: 0, b: 50, c: 50 }, "a", 99), { a: 99, b: 1, c: 0 })
})

test("integer slider positions keep the group total at 100", () => {
  for (const current of [{ a: 34, b: 26, c: 22, d: 18 }, { a: 100, b: 0, c: 0, d: 0 }]) {
    for (const key of Object.keys(current)) {
      for (let value = 0; value <= 100; value++) {
        const next = updatePercentWeight(current, key, value)
        assert.equal(next[key], value)
        assert.equal(Object.values(next).reduce((sum, item) => sum + item, 0), 100)
        assert.ok(Object.values(next).every((item) => Number.isInteger(item) && item >= 0))
      }
    }
  }
})
