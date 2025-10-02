output "vpc_id" {
  description = "ID of the created VPC"
  value       = module.vpc.vpc_id
}

output "ecs_cluster_id" {
  description = "Identifier of the ECS cluster"
  value       = module.ecs.cluster_id
}

output "rds_endpoint" {
  description = "Endpoint address for the RDS instance"
  value       = module.rds.endpoint
}

output "monitoring_dashboard_url" {
  description = "URL for the monitoring dashboard"
  value       = module.monitoring.dashboard_url
}
