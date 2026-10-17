import type { LabData } from '@/types/lab'

const object = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value)
const number = (value: unknown) => typeof value === 'number' && Number.isFinite(value)
const text = (value: unknown) => typeof value === 'string' && value.length > 0
const metrics = (value: unknown) => object(value) &&
  ['due', 'paired', 'coverage', 'signal_rate', 'independent'].every(key => number(value[key])) &&
  ['mean_delta_pp', 'lower_delta_pp', 'mean_return_pct', 'mean_excess_pp', 'stress_excess_pp', 'worst_period_pct']
    .every(key => value[key] === null || number(value[key]))

export function isLabData(value: unknown): value is LabData {
  if (!object(value) || value.schema_version !== 1 || !object(value.policy) || !text(value.generated_at) ||
    !text(value.policy_hash) || !text(value.review_workflow)) return false
  const policy = value.policy
  if (!['horizon', 'spawn_after', 'max_active', 'max_trials', 'max_generations', 'children_per_parent', 'cost_bps',
    'stress_cost_bps', 'min_coverage', 'min_independent_periods', 'min_signal_rate'].every(key => number(policy[key])) ||
    !Array.isArray(policy.checkpoints) || !policy.checkpoints.length || !policy.checkpoints.every(number)) return false
  if (!Array.isArray(value.parents) || !value.parents.every(parent => object(parent) &&
    ['id', 'root_id', 'name', 'market', 'source_version'].every(key => text(parent[key])) && number(parent.matured))) return false
  if (!Array.isArray(value.trials) || !value.trials.every(trial => object(trial) &&
    ['id', 'root_id', 'parent_id', 'market', 'source_version', 'created_at', 'name', 'hypothesis', 'expected', 'definition_hash'].every(key => text(trial[key])) &&
    number(trial.generation) && ['testing', 'review', 'rejected', 'approved', 'paused'].includes(String(trial.status)) &&
    object(trial.params) && (trial.metrics === undefined || metrics(trial.metrics)) &&
    object(trial.change) && text(trial.change.parameter) && number(trial.change.from) && number(trial.change.to) &&
    Array.isArray(trial.assessments) && trial.assessments.every(assessment => object(assessment) && number(assessment.checkpoint) &&
      text(assessment.hash) && object(assessment.gates) && Object.values(assessment.gates).every(gate => typeof gate === 'boolean')))) return false
  if (!Array.isArray(value.events) || !value.events.every(event => object(event) && text(event.trial_id) && text(event.action) && text(event.at))) return false
  return Array.isArray(value.observations) && value.observations.every(row => object(row) && text(row.trial_id) &&
    number(row.entry_date) && typeof row.due === 'boolean' && object(row.branch) && object(row.parent))
}
