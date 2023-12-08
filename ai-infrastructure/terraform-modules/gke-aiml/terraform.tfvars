# Copyright 2023 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

project_id          = "jk-mlops-dev"
prefix              = "jk-saxml"
region              = "us-central2"
deletion_protection = false

gcs_configs = {
  admin-bucket     = {}
  model-repository = {}
}

cluster_config = {
  name                = "gke-cluster"
  workloads_namespace = "saxml-workloads"
}


cpu_node_pools = {
  primary-cpu-node-pool = {
    zones          = ["us-central2-b"]
    min_node_count = 1
    max_node_count = 3
    machine_type   = "n1-standard-8"
  }

  saxml-admin-node-pool = {
    zones          = ["us-central2-b"]
    min_node_count = 3
    max_node_count = 3
    machine_type   = "n1-standard-8"
    taints = {
      saxml-admin-node-pool = {
        value  = true
        effect = "NO_SCHEDULE"
      }
    }
    labels = {
      saxml-admin-node-pool = true
    }
  }

  large-cpu-workload-node-pool = {
    zones          = ["us-central2-a"]
    min_node_count = 0
    max_node_count = 3
    machine_type   = "n2-highmem-32"
    disk_size_gb   = 500
    labels = {
      checkpoint-converter-node-pool = true
    }
  }
}

tpu_node_pools = {
  tpu-v4-8-node-pool = {
    zones          = ["us-central2-b"]
    min_node_count = 1
    max_node_count = 1
    tpu_type       = "v4-8"
    labels = {
      saxml-model-server-pool = true
    }
  }
}

vpc_config = {
  network_name           = "network"
  subnet_name            = "subnet"
  subnet_ip_cidr_range   = "10.129.0.0/24"
  pods_ip_cidr_range     = "192.168.64.0/20"
  services_ip_cidr_range = "192.168.80.0/20"
}

###### Examples of optional configurations #####

### Existing service accounts ###
#node_pool_sa = {
#  email = "gke-saxml-sa-test@jk-mlops-dev.iam.gserviceaccount.com"
#}
#wid_sa = {
#  email       = "wid-saxml-sa-test@jk-mlops-dev.iam.gserviceaccount.com"
#}



### Using existing VPC
#vpc_ref = {
#  host_project           = "jk_mlops_dev"
#  network_self_link      = "https://www.googleapis.com/compute/v1/projects/jk-mlops-dev/global/networks/jk-gke-network-test"
#  subnet_self_link       = "https://www.googleapis.com/compute/v1/projects/jk-mlops-dev/regions/us-central2/subnetworks/jk-gke-subnet-test"
#  pods_ip_range_name     = "ip-range-pods"
#  services_ip_range_name = "ip-range-services"
#}


