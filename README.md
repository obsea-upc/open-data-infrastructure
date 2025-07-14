# Open Data Infrastructure #

**Open Data Infrastructure** is a modular, containerized framework to deploy a full-fledged data management infrastructure tailored for scientific marine data acquisition systems following the FAIR principles.  It bundles reverse proxying, file serving, real‑time sensor APIs, historical data access, monitoring, visualization, and data cataloging into one cohesive stack.

---

## 🚀 Features

- **Reverse Proxy (NGINX)**  
  Route HTTP(s) traffic by hostname/path to the appropriate backend service, terminate SSL, and manage rate‑limiting & caching.

- **File Server (NGINX)**  
  Serve raw data files (NetCDF, CSV, JPEG, etc.) via a lightweight HTTP file server with directory browsing.

- **SensorThings API (FROST‑Server)**  
  OGC‐compliant SensorThings implementation for ingesting and querying real‑time IoT sensor streams (HTTP & MQTT).

- **ERDDAP**  
  Publish multidimensional scientific datasets with subsetting, aggregation, and on‑the‑fly format conversion (NetCDF, CSV, JSON, etc.).

- **Zabbix**  
  Infrastructure monitoring for all containers and hosts: metrics, alerts, and performance dashboards.

- **Grafana**  
  Customizable dashboards to visualize time‑series data from Zabbix, InfluxDB, PostgreSQL, and SensorThings.

- **CKAN**  
  A data catalog/repository to publish, tag, and share datasets with RESTful APIs and web front‑end.

- **pgAdmin**  
  Web‑based administration for PostgreSQL databases.

- **MMAPI**  
  Marine Metadata API to maintain the sensors and platform metadata, including deployments, recoveries, projects and more.

---

## Setup Process

### Prerequisities:

* super-user permissions
* apt-get 

Follow these steps to install and configure the **Open Data Infrastructure** stack on your system.

### 1. 📥 Download and Run the Setup Script

This script will install required dependencies and initialize the project structure.

```bash
curl https://raw.githubusercontent.com/obsea-upc/open-data-infrastructure/refs/heads/main/installer.sh -o setup.sh
chmod 755 setup.sh
./setup.sh  # Do not run as sudo! the script will ask for sudo permissions if needed
```

### 2. ⚙️ Configure Infrastructure and Secrets

After running the setup script, ODI will be copied into `/opt/odi`. You will need to customize two key configuration files:
* `/opt/odi/infrastructure.yaml`
* `/opt/odi/secrets.env`


The `infrastructure.yaml` defines your infrastructure layout — server addresses, service ports, domain names, and networking options. Edit infrastructure.yaml with your preferred settings using any text editor:
```bash
cd /opt/odi
cp infrastructure.yaml.template infrastructure.yaml
vim infrastructure.yaml
```

 The `secrets.yaml` stores environment variables such as database passwords, API keys, and admin credentials.

```bash
cp secrets.env.template secrets.env
vim secrets.env
```

### 3. 🚀 Launch the Infrastructure

Once everything is configured you can launch the all the services using ODI's command-line interface: 

```bash
odi setup
odi up
```

`odi setup` validates and prepares the configuration, `odi up` brings up the full stack using Docker Compose.

You should now be able to access the services via the URLs configured in your infrastructure.yaml file.


### Contact info ###

* **author**: Enoc Martínez  
* **version**: 0.0.1
* **organization**: Universitat Politècnica de Catalunya (UPC)  
* **contact**: enoc.martinez@upc.edu  

