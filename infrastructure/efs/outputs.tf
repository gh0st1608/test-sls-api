output "access_point_arn" {
  value = aws_efs_access_point.access-point.arn
}

output "efs_mount_target" {
  value = aws_efs_mount_target.mount
}