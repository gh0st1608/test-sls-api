output "ec2_instance_id" {
  value = aws_instance.slsserver.id
}

output "public_ip" {
  value = aws_instance.slsserver.public_ip
} 

output "subnet_id" {
  value = aws_instance.slsserver.subnet_id
}