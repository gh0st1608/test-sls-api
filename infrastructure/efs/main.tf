resource "aws_efs_file_system" "efs" {
  tags = {
    Name = "efs-similarity"
  }
  #availability_zone_name = "us-east-1e"
}

resource "aws_efs_mount_target" "mount" {
  #count           = 2
  file_system_id = aws_efs_file_system.efs.id
  subnet_id      = var.subnet_private_id
  
  security_groups = [var.seg_group_lambda_id]
}

resource "aws_efs_access_point" "access-point" {
  file_system_id = aws_efs_file_system.efs.id

  posix_user {
    gid = 1000
    uid = 1000
  }

  root_directory {
    path = "/"
    creation_info {
      owner_gid   = 1000
      owner_uid   = 1000
      permissions = "777"
    }
  }

  tags = {
    Name = "lambda-access-point"
  }
}

resource "null_resource" "configure_nfs" {
  depends_on = [aws_efs_mount_target.mount]
  connection {
    type     = "ssh"
    user     = "ubuntu"
    private_key = file("chupetex.pem")
    agent = false
    host     = var.public_ip
  }
  provisioner "remote-exec" {
    inline = [
      "sudo apt-get update -y",
      "sudo apt install nfs-common -y",
      "sudo apt install libpq-dev -y",
      #"sudo apt install python3.8 -y",
      "sudo apt install python3-pip -y",
      "echo ${aws_efs_file_system.efs.dns_name}",
      "sudo mkdir -p efs",
      #"sudo mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport ${aws_efs_file_system.efs.dns_name}:/ efs",
      #"sudo mount -t nfs4 -o nfsvers=4.1,rsize=1048576,wsize=1048576,hard,timeo=600,retrans=2,noresvport fs-0da3e3f235315f978.efs.us-east-1.amazonaws.com:/ efs",
      "sudo chmod -R 777 /home/ubuntu/efs",
      "pip3 install testresources",
      #"pip3 install --upgrade --target /home/ubuntu/efs psycopg2-binary scikit-learn mysql-connector-python openai pandas requests pdfminer.six numpy"
    ]
  }
}