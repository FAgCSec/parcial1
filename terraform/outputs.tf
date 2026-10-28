# Infraestructura como Código (IaC)

## Proyecto: HeavyCult Dropshipping — Terraform Outputs

output "project_name" {
  description = "Nombre del proyecto"
  value       = var.project_name
}

output "environment" {
  description = "Entorno de despliegue"
  value       = var.environment
}

output "mongodb_cluster_id_primary" {
  description = "ID del cluster MongoDB primario"
  value       = mongodbatlas_cluster.primary.id
}

output "mongodb_cluster_id_secondary" {
  description = "ID del cluster MongoDB secundario (DR)"
  value       = mongodbatlas_cluster.secondary.id
}

output "mongodb_primary_uri" {
  description = "URI de conexión MongoDB primario"
  value       = mongodbatlas_cluster.primary.connection_strings[0].standard_srv
  sensitive   = true
}

output "mongodb_secondary_uri" {
  description = "URI de conexión MongoDB secundario"
  value       = mongodbatlas_cluster.secondary.connection_strings[0].standard_srv
  sensitive   = true
}

output "s3_buckets" {
  description = "Todos los buckets S3 del Data Lake"
  value = {
    raw       = aws_s3_bucket.raw.bucket
    processed = aws_s3_bucket.processed.bucket
    curated   = aws_s3_bucket.curated.bucket
    raw_dr    = aws_s3_bucket.raw_dr.bucket
    processed_dr = aws_s3_bucket.processed_dr.bucket
    curated_dr = aws_s3_bucket.curated_dr.bucket
  }
}

output "vpc_cidr" {
  description = "CIDR block de la VPC"
  value       = aws_vpc.primary.cidr_block
}

output "vpc_id" {
  description = "ID de la VPC primaria"
  value       = aws_vpc.primary.id
}

output "security_group_ids" {
  description = "IDs de los security groups"
  value = {
    mongodb = aws_security_group.mongodb.id
    data_lake = aws_security_group.data_lake.id
  }
}

output "cloudwatch_alarm_names" {
  description = "Nombres de las alarmas de CloudWatch"
  value = {
    replication_lag    = aws_cloudwatch_metric_alarm.replication_lag.alarm_name
    storage_high       = aws_cloudwatch_metric_alarm.storage_utilization.alarm_name
    s3_replication_lag = aws_cloudwatch_metric_alarm.s3_replication_lag.alarm_name
  }
}

output "sns_topic_arn" {
  description = "ARN del topic SNS para alertas"
  value       = aws_sns_topic.alerts.arn
}

output "data_lake_config" {
  description = "Configuración completa del Data Lake"
  value = {
    layers = ["raw", "processed", "curated"]
    regions = [var.region_primary, var.region_secondary]
    replication_enabled = var.enable_cross_region_replication
    backup_retention_days = {
      raw      = 365
      processed = 90
      curated   = 1825
    }
    storage_classes = {
      raw      = ["STANDARD", "STANDARD_IA", "GLACIER_IR"]
      processed = ["STANDARD", "STANDARD_IA"]
      curated   = ["STANDARD", "GLACIER"]
    }
  }
}

output "terraform_infrastructure_summary" {
  description = "Resumen de la infraestructura desplegada"
  value = <<-EOT
    ╔══════════════════════════════════════════════════╗
    ║  HeavyCult Dropshipping - Infrastructure        ║
    ╠══════════════════════════════════════════════════╣
    ║  MongoDB Atlas Primary: ${var.mongodb_cluster_tier}  (${var.region_primary})  ║
    ║  MongoDB Atlas DR:      ${var.mongodb_cluster_dr_tier}  (${var.region_secondary})  ║
    ║  S3 Buckets:  3 capas x 2 regiones = 6 buckets  ║
    ║  VPC:         ${var.cidr_block}               ║
    ║  CloudWatch:  3 alarmas configuradas            ║
    ║  SNS:         Alertas DR activadas              ║
    ╚══════════════════════════════════════════════════╝
  EOT
}
