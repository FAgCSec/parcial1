# Infraestructura como Código (IaC)

## Proyecto: HeavyCult Dropshipping — Terraform Configuration

### Archivo: main.tf

terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source                = "hashicorp/aws"
      version               = "~> 5.0"
      configuration_aliases = [aws.primary, aws.secondary]
    }
    mongodbatlas = {
      source  = "mongodb/mongodbatlas"
      version = "~> 1.0"
    }
  }

  backend "s3" {
    bucket         = "heavycult-terraform-state"
    key            = "heavycult/data-lake/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "terraform-locks"
    encrypt        = true
  }
}

# ============================================================
# PROVIDERS
# ============================================================

provider "aws" {
  alias   = "primary"
  region  = var.region_primary
  profile = "default"
}

provider "aws" {
  alias   = "secondary"
  region  = var.region_secondary
  profile = "default"
}

provider "mongodbatlas" {
  project_id = var.mongodb_atlas_project_id
}

# ============================================================
# VPC - REGIÓN PRIMARIA
# ============================================================

resource "aws_vpc" "primary" {
  provider             = aws.primary
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(var.tags, {
    Name = "${var.project_name}-vpc-primary"
  })
}

resource "aws_subnet" "primary_public" {
  provider             = aws.primary
  vpc_id               = aws_vpc.primary.id
  cidr_block           = "10.0.1.0/24"
  availability_zone    = "${var.region_primary}a"
  map_public_ip_on_launch = true

  tags = merge(var.tags, {
    Name = "public-subnet"
  })
}

resource "aws_subnet" "primary_private" {
  provider             = aws.primary
  vpc_id               = aws_vpc.primary.id
  cidr_block           = "10.0.2.0/24"
  availability_zone    = "${var.region_primary}a"

  tags = merge(var.tags, {
    Name = "private-subnet"
  })
}

resource "aws_internet_gateway" "primary" {
  provider = aws.primary
  vpc_id   = aws_vpc.primary.id

  tags = merge(var.tags, {
    Name = "igw-primary"
  })
}

# ============================================================
# VPC - REGIÓN SECUNDARIA (DR)
# ============================================================

resource "aws_vpc" "secondary" {
  provider             = aws.secondary
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = merge(var.tags, {
    Name = "${var.project_name}-vpc-secondary"
  })
}

resource "aws_subnet" "secondary_private" {
  provider             = aws.secondary
  vpc_id               = aws_vpc.secondary.id
  cidr_block           = "10.0.2.0/24"
  availability_zone    = "${var.region_secondary}a"

  tags = merge(var.tags, {
    Name = "dr-private-subnet"
  })
}

# ============================================================
# SEGURIDAD - SECURITY GROUPS
# ============================================================

resource "aws_security_group" "mongodb" {
  provider    = aws.primary
  name        = "mongodb-sg"
  description = "Security group para MongoDB Atlas"
  vpc_id      = aws_vpc.primary.id

  ingress {
    from_port   = 27017
    to_port     = 27017
    protocol    = "tcp"
    cidr_blocks = [var.cidr_block]
    description = "MongoDB traffic"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "mongodb-sg"
  })
}

resource "aws_security_group" "data_lake" {
  provider    = aws.primary
  name        = "data-lake-sg"
  description = "Security group para Data Lake S3 access"
  vpc_id      = aws_vpc.primary.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.cidr_block]
    description = "S3 HTTPS access"
  }

  tags = merge(var.tags, {
    Name = "data-lake-sg"
  })
}

# ============================================================
# MONGODB ATLAS - CLUSTER PRINCIPAL
# ============================================================

resource "mongodbatlas_cluster" "primary" {
  provider = mongodbatlas

  project_id = var.mongodb_atlas_project_id
  name       = "heavycult-primary"

  cluster_type   = "REPLICASET"
  provider_name  = "AWS"
  provider_region_name = var.region_primary
  instance_size_name   = var.mongodb_cluster_tier

  backup_enabled        = true
  auto_scaling_compute_enabled = true
  auto_scaling_disk_enabled  = true

  disk_size_gb = 100

  replication_specs {
    num_shards = 1
    num_members = 3
    regions_config {
      region_name      = var.region_primary
      electable_members = 1
      priority         = 7
      tags           = { "Tier": "Primary" }
    }
    regions_config {
      region_name      = var.region_secondary
      electable_members = 1
      priority         = 3
      tags           = { "Tier": "Secondary" }
    }
    regions_config {
      region_name      = var.region_secondary
      electable_members = 0
      priority         = 1
      tags           = { "Tier": "DR" }
    }
  }

  provider_instance_profile_name = "AtlasAWSDefaultAccessRole"

  skip_upgrade_version = false

  tags = merge(var.tags, {
    Name = "heavycult-primary-cluster"
  })
}

# ============================================================
# MONGODB ATLAS - CLUSTER DR
# ============================================================

resource "mongodbatlas_cluster" "secondary" {
  provider = mongodbatlas

  project_id = var.mongodb_atlas_project_id
  name       = "heavycult-dr"

  cluster_type   = "REPLICASET"
  provider_name  = "AWS"
  provider_region_name = var.region_secondary
  instance_size_name   = var.mongodb_cluster_dr_tier

  backup_enabled        = true
  auto_scaling_compute_enabled = false
  auto_scaling_disk_enabled  = false

  disk_size_gb = 50

  replication_specs {
    num_shards = 1
    num_members = 2
    regions_config {
      region_name      = var.region_secondary
      electable_members = 1
      priority         = 7
      tags           = { "Tier": "DR-Primary" }
    }
    regions_config {
      region_name      = var.region_secondary
      electable_members = 0
      priority         = 1
      tags           = { "Tier": "Arbiter" }
    }
  }

  provider_instance_profile_name = "AtlasAWSDefaultAccessRole"

  skip_upgrade_version = false

  tags = merge(var.tags, {
    Name = "heavycult-dr-cluster"
  })
}

# ============================================================
# MONGODB ATLAS - USUARIOS Y BASES DE DATOS
# ============================================================

resource "mongodbatlas_database_user" "admin" {
  provider = mongodbatlas

  project_id = var.mongodb_atlas_project_id
  username   = var.admin_username
  password   = var.admin_password
  roles      = ["GROUP_READ_WRITE", "ATLAS_ADMIN"]
}

resource "mongodbatlas_project" "primary" {
  provider = mongodbatlas

  name       = var.project_name
  org_id     = var.mongodb_atlas_org_id
  is_data_cache_enabled = true

  tags = var.tags
}

# ============================================================
# DATA LAKE - S3 BUCKETS (RAW, PROCESSED, CURATED)
# ============================================================

# --- RAW LAYER ---
resource "aws_s3_bucket" "raw" {
  provider = aws.primary
  bucket   = "${var.data_lake_bucket_name}-raw"

  tags = merge(var.tags, {
    Name      = "Data Lake - Raw Layer"
    Tier      = "Bronze"
    Layer     = "Raw"
  })
}

resource "aws_s3_bucket_versioning" "raw" {
  provider = aws.primary
  bucket   = aws_s3_bucket.raw.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  provider = aws.primary
  bucket   = aws_s3_bucket.raw.id

  rule {
    id     = "transition-to-ia"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }

    expiration {
      days = 365
    }
  }
}

# --- PROCESSED LAYER ---
resource "aws_s3_bucket" "processed" {
  provider = aws.primary
  bucket   = "${var.data_lake_bucket_name}-processed"

  tags = merge(var.tags, {
    Name      = "Data Lake - Processed Layer"
    Tier      = "Silver"
    Layer     = "Processed"
  })
}

resource "aws_s3_bucket_versioning" "processed" {
  provider = aws.primary
  bucket   = aws_s3_bucket.processed.id

  versioning_configuration {
    status = "Enabled"
  }
}

# --- CURATED LAYER ---
resource "aws_s3_bucket" "curated" {
  provider = aws.primary
  bucket   = "${var.data_lake_bucket_name}-curated"

  tags = merge(var.tags, {
    Name      = "Data Lake - Curated Layer"
    Tier      = "Gold"
    Layer     = "Curated"
  })
}

resource "aws_s3_bucket_versioning" "curated" {
  provider = aws.primary
  bucket   = aws_s3_bucket.curated.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "curated" {
  provider = aws.primary
  bucket   = aws_s3_bucket.curated.id

  rule {
    id     = "transition-to-glacier"
    status = "Enabled"

    transition {
      days          = 60
      storage_class = "GLACIER"
    }

    expiration {
      days = 1825
    }
  }
}

# ============================================================
# S3 CROSS-REGION REPLICATION
# ============================================================

resource "aws_s3_bucket" "raw_dr" {
  provider = aws.secondary
  bucket   = "${var.data_lake_bucket_name}-raw-dr"

  tags = merge(var.tags, {
    Name = "Data Lake - Raw Layer DR"
  })
}

resource "aws_s3_bucket" "processed_dr" {
  provider = aws.secondary
  bucket   = "${var.data_lake_bucket_name}-processed-dr"

  tags = merge(var.tags, {
    Name = "Data Lake - Processed Layer DR"
  })
}

resource "aws_s3_bucket" "curated_dr" {
  provider = aws.secondary
  bucket   = "${var.data_lake_bucket_name}-curated-dr"

  tags = merge(var.tags, {
    Name = "Data Lake - Curated Layer DR"
  })
}

resource "aws_s3_bucket_replication_configuration" "raw_replication" {
  provider = aws.primary
  bucket   = aws_s3_bucket.raw.id
  role     = aws_iam_role.s3_replication.arn

  rule {
    id       = "raw-replication"
    status   = var.enable_cross_region_replication ? "Enabled" : "Disabled"
    priority = 1

    destination {
      bucket        = aws_s3_bucket.raw_dr.arn
      storage_class = "STANDARD"
    }

    filter {
      prefix = ""
    }
  }
}

# ============================================================
# IAM - ROLES Y POLÍTICAS
# ============================================================

resource "aws_iam_role" "s3_replication" {
  provider = aws.primary
  name     = "s3-cross-region-replication-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "s3_replication_policy" {
  provider = aws.primary
  name     = "s3-replication-policy"
  role     = aws_iam_role.s3_replication.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.raw.arn,
          aws_s3_bucket.processed.arn,
          aws_s3_bucket.curated.arn
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:GetObjectVersion",
          "s3:GetObjectVersionAcl"
        ]
        Resource = [
          "${aws_s3_bucket.raw.arn}/*",
          "${aws_s3_bucket.processed.arn}/*",
          "${aws_s3_bucket.curated.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags",
          "s3:GetObjectVersionTagging",
          "s3:ObjectOwnerOverrideToBucketOwner"
        ]
        Resource = [
          "${aws_s3_bucket.raw_dr.arn}/*",
          "${aws_s3_bucket.processed_dr.arn}/*",
          "${aws_s3_bucket.curated_dr.arn}/*"
        ]
      }
    ]
  })
}

resource "aws_iam_role" "lambda_backup" {
  provider = aws.primary
  name     = "data-lake-backup-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })
}

# ============================================================
# CLOUDWATCH - MONITOREO Y ALARMAS
# ============================================================

resource "aws_cloudwatch_log_group" "mongodb" {
  provider = aws.primary
  name     = "/mongodb/heavycult"
  retention_in_days = 90
}

resource "aws_cloudwatch_log_group" "data_lake" {
  provider = aws.primary
  name     = "/data-lake/heavycult"
  retention_in_days = 90
}

resource "aws_cloudwatch_metric_alarm" "replication_lag" {
  provider          = aws.primary
  alarm_name        = "mongo-replication-lag-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "MongoDBReplLatency"
  namespace           = "AWS/MongoDB"
  period              = 300
  statistic           = "Average"
  threshold           = 10
  alarm_description   = "Alert when MongoDB replication lag exceeds 10 seconds"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "storage_utilization" {
  provider          = aws.primary
  alarm_name        = "mongo-storage-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "MongoDBClusterStorageUsed"
  namespace           = "AWS/MongoDB"
  period              = 300
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "Alert when MongoDB storage utilization exceeds 80%"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_cloudwatch_metric_alarm" "s3_replication_lag" {
  provider          = aws.primary
  alarm_name        = "s3-replication-lag-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "S3ReplLatency"
  namespace           = "AWS/S3"
  period              = 300
  statistic           = "Average"
  threshold           = 300
  alarm_description   = "Alert when S3 replication lag exceeds 5 minutes"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

# ============================================================
# SNS - NOTIFICACIONES
# ============================================================

resource "aws_sns_topic" "alerts" {
  provider = aws.primary
  name     = "heavycult-dr-alerts"

  tags = merge(var.tags, {
    Name = "DR Alert Notifications"
  })
}

resource "aws_sns_topic_subscription" "email" {
  provider  = aws.primary
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = "admin@heavycult.com"
}

# ============================================================
# OUTPUTS
# ============================================================

output "mongodb_primary_connection_string" {
  description = "Connection string para MongoDB primario"
  value       = mongodbatlas_cluster.primary.connection_strings[0].standard
  sensitive   = true
}

output "mongodb_secondary_connection_string" {
  description = "Connection string para MongoDB secundario (DR)"
  value       = mongodbatlas_cluster.secondary.connection_strings[0].standard
  sensitive   = true
}

output "s3_raw_bucket" {
  description = "Nombre del bucket S3 para datos raw"
  value       = aws_s3_bucket.raw.bucket
}

output "s3_processed_bucket" {
  description = "Nombre del bucket S3 para datos processed"
  value       = aws_s3_bucket.processed.bucket
}

output "s3_curated_bucket" {
  description = "Nombre del bucket S3 para datos curated"
  value       = aws_s3_bucket.curated.bucket
}



output "security_group_mongodb" {
  description = "ID del security group de MongoDB"
  value       = aws_security_group.mongodb.id
}
