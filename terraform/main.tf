terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

module "vpc" {
  source = "./modules/vpc"

  cidr_block  = var.vpc_cidr
  environment = var.environment
}

module "ecs" {
  source = "./modules/ecs"

  vpc_id    = module.vpc.vpc_id
  subnets   = module.vpc.private_subnets
  environment = var.environment
}

module "rds" {
  source = "./modules/rds"

  vpc_id         = module.vpc.vpc_id
  subnets        = module.vpc.database_subnets
  instance_class = var.db_instance_class
  environment    = var.environment
}

module "monitoring" {
  source = "./modules/monitoring"

  environment = var.environment
  alarm_email = var.ops_email
}
