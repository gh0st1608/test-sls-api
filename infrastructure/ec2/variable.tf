variable "ami_id" {
  default = "ami-0261755bbcb8c4a84"
}

variable "instance_type" {
  default = "t2.small"
}

variable "seg_group_lambda_id" {
  type = string
}

/* variable "subnet_private_id" {
  type = string
} */

variable "subnet_public_id" {
  type = string
}

variable "key_name" {
  type = string
}