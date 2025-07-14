nginx_conf_start = """
events {
}
http {
"""

nginx_conf_end = """
}
"""

nginx_server_start = """
  server {{
    server_name {dns};
    listen 80;
    listen 443 ssl;
    ssl_certificate /ssl_keys/ssl_certificate.pem;
    ssl_certificate_key /ssl_keys/ssl_certificate.key;
    client_max_body_size 2048M;
    ssl_session_cache builtin:1000 shared:SSL:10m; # Defining option to share SSL Connection with Passed Proxy
    ssl_protocols   TLSv1 TLSv1.1 TLSv1.2 TLSv1.3;  # Defining used protocol versions.
    ssl_ciphers HIGH:!aNULL:!eNULL:!EXPORT:!CAMELLIA:!DES:!MD5:!PSK:!RC4; # Defining ciphers to use.
    ssl_prefer_server_ciphers on; # Enabling ciphers      
"""

nginx_server_end = """
  }
"""

erddap_config = """

    # ERDDAP config
    location /erddap {{
      proxy_pass http://{ip}:{port}/erddap;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
      proxy_set_header X-Forwarded-Server $host;
      proxy_set_header X-Forwarded-Host $host;
      proxy_set_header Host $host;
    }}
"""

sensorthings_config = """

    # SensorThings config
    location /FROST-Server {{
      proxy_set_header HOST $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_pass http://{ip}:{port}/FROST-Server;
    }}
"""

sensorthings_timeseries_config = """
    location /sta-timeseries {{
       proxy_pass http://{ip}:{port}/sta-timeseries;
       proxy_set_header HOST $host;
       proxy_set_header X-Real-IP $remote_addr;
    }}
"""

grafana_config = """

     # Grafana
     location /grafana {{
         proxy_pass http://{ip}:{port}/grafana;
        proxy_set_header Host $http_host;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }}
"""


ckan_config = """

      # CKAN
      location / {{
          proxy_pass http://{ip}:{port};
          proxy_set_header X-Real-IP $remote_addr;
          proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
          proxy_set_header X-Forwarded-Server $host;
          proxy_set_header X-Forwarded-Host $host;
          proxy_set_header Host $host;
      }}
"""

zabbix_config = """

       # Zabbix 
       location / {{
           proxy_pass http://{ip}:{port};
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
           proxy_set_header X-Forwarded-Server $host;
           proxy_set_header X-Forwarded-Host $host;
           proxy_set_header Host $host;
       }}  
"""

fileserver_config = """
    # FileServer config
    location / {{
      proxy_set_header HOST $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_pass http://{ip}:{port};
    }}
"""

pgadmin_config = """
     location /pgadmin/ {{
        proxy_set_header X-Script-Name /pgadmin;
        proxy_set_header X-Scheme $scheme;
        proxy_set_header Host $host;
        proxy_pass http://{ip}:{port}/;
        proxy_redirect off;
    }}
"""


mmapi_config = """
    location /mmapi/ {{
      proxy_set_header HOST $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_pass http://{ip}:{port}/mmapi/;
    }}
"""

goaccess_config = """
     location /goaccess/ {{    
        root /var/goaccess;
        index report.html;
        try_files /report.html =404;    
    }}
"""


def service_nginx_config(name):
    config = {
        "grafana": grafana_config,
        "erddap": erddap_config,
        "sensorthings": sensorthings_config,
        "sta-master": sensorthings_config,
        "sta-slave": sensorthings_config,
        "sta-ts-master": sensorthings_timeseries_config,
        "sta-ts-slave": sensorthings_timeseries_config,
        "zabbix": zabbix_config,
        "ckan": ckan_config,
        "fileserver": fileserver_config,
        "pgadmin": pgadmin_config,
        "mmapi": mmapi_config,
        "goaccess": goaccess_config
    }

    if name not in config.keys():
        # Maybe it's a subset? like proxy-upc for proxy
        if "-" in name and name.split("-")[0] in config.keys():
            config[name] = config[name.split("-")[0]]

    if name not in config.keys():
        raise ValueError(f"NGINX configuration for service '{name}' not implemented!")
    return config[name]