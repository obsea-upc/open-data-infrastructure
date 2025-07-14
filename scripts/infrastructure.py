from multiprocessing.managers import Value

import yaml
import os
import rich
import traceback
import json
import getpass
import docker


try:
    from utils import check_optional_keys, check_required_keys, run_subprocess, run_subprocess_pipe
    from nginx import nginx_server_start, service_nginx_config, nginx_conf_start, nginx_server_end, nginx_conf_end
except ModuleNotFoundError:
    from .utils import check_optional_keys, check_required_keys, run_subprocess, run_subprocess_pipe
    from .nginx import nginx_server_start, service_nginx_config, nginx_conf_start, nginx_server_end, nginx_conf_end



class Volume:
    def __init__(self, config, path, user):
        """
        This class provides a high-evel view of Volumes in ODI
        :param config:
        :param path:
        """
        self.type = "folder"  # can be folder or file
        self.odi_managed = False  # This flag manage
        self.user = user
        self.expected_permissions = ""
        try:
            self.source, self.destination = config.split(":")  # split src:dest

        except ValueError:
            self.source, self.destination, perm = config.split(":")  # split src:dest:permissions
            if perm == "ro":
                self.odi_managed = False  # by default, do not create the volume

        self.odi_managed = False  # by default, do not create the volume

        # If basename contains a . we assume that it is a file and doesn't need to be created
        if "." in os.path.basename(self.destination):
            self.type = "file"
            self.odi_managed = False

        elif self.source.startswith("/tmp/") or self.source.startswith("/var/temp"):
            # temporal folder to transfer data
            self.odi_managed = True
            self.expected_permissions = "777"

        elif self.source.startswith("./volumes/"):
            # volume not following ODI conventions, skipping
            self.odi_managed = True

        if self.source.startswith("./"):
            self.source = self.source[2:]

        # Convert from relative to absolute path
        if not self.source.startswith("/"):
            self.source = os.path.join(path, self.source)

    def setup(self):
        if not self.odi_managed:
            return

        rich.print(f"       setting up Volume  {self.source}:{self.destination}")
        if os.path.exists(self.source):
            return

        try:
            run_subprocess(f"mkdir -p {self.source}", quiet=True)
        except ValueError:
            # Try it as sudo and change the owner later
            run_subprocess(f"sudo mkdir -p {self.source}")
            run_subprocess(f"sudo chown {os.getuid()}:{os.getuid()} {self.source}")

        if self.expected_permissions:
            rich.print(f"        changing permissions to {self.expected_permissions}")
            run_subprocess(f"sudo chmod {self.expected_permissions} {self.source}")

        if self.user:
            rich.print(f"        changing owner to {self.user}")
            run_subprocess(f"sudo chown {self.user}:{self.user} {self.source}")

    def remove(self):
        if not self.odi_managed:
            return
        rich.print(f"[red]Removing {self.source}, continue?")
        input()

        run_subprocess(f"sudo rm -rf {self.source}")


class Container:
    def __init__(self, service_name, conf, path):
        """
        Contains the configuration info for a single container
        """
        assert isinstance(conf, dict), f"expected dict, got {type(conf)}"
        self.container_name = conf["container_name"]

        try:
            self.image = conf["image"]
        except KeyError:
            raise ValueError(f"Image not specified for container {service_name}")

        self.requires_build = False
        self.user = ""
        self.networks = []
        self.volumes = []
        self.path = path
        self.service_name = service_name

        if "user" in conf.keys():
            self.user = conf["user"]

        if "networks" in conf.keys():
            self.networks += conf["networks"]

        if "build" in conf.keys():
            self.requires_build = True

        if "volumes" in conf.keys():
            for v in conf["volumes"]:
                self.volumes.append(Volume(v, path, self.user))


    def setup(self):
        # Creating volumes
        rich.print(f"       setting up container '{self.container_name}'")

        for v in self.volumes:
            v.setup()

    def build(self):
        if not self.requires_build:
            return
        # Check if there's an image with that name
        dclient = docker.from_env()
        images = dclient.images.list()
        image_names = []
        for img in images:
            if len(img.tags) == 0:
                continue
            name = img.tags[0]
            if "/" in name:
                name = name.split("/")[1]
            name = name.split(":")[0]
            image_names.append(name)

        if self.container_name in image_names:
            # no need to build the container, already an image created
            rich.print(f"Image '{self.image}' already built")
            return
        rich.print(f"Building image: '{self.image}'")
        run_subprocess(f"docker compose build {self.service_name}")



    def remove(self):

        dclient = docker.from_env()
        # Remove image
        if self.requires_build:
            try:
                img = dclient.images.get(self.image)
                rich.print(f"      removing image: {self.image}")
                img.remove()
            except docker.errors.NotFound:
                rich.print(f"[yellow]      image not found: {self.image}")
                pass

        for v in self.volumes:
            v.remove()


class Service:
    def __init__(self, path, force_ownerships={}):
        """
        Parses a docker-compose file defining a service. Each service may have one or more containers
        :param filename: docker-compose file
        :param force_ownerships: ownerships of docker volumes. Useful for multi-user containers key=path value=owner
        """
        self.path = path
        self.docker_compose = os.path.join(path, "docker-compose.yaml")
        self.containers = []
        self.networks = []
        self.name = os.path.basename(path)
        self.force_ownerships = force_ownerships
        if not os.path.exists(self.docker_compose):
            raise FileNotFoundError(f"{self.docker_compose} does not exist")

        with open(self.docker_compose) as f:
            compose = yaml.safe_load(f)

        for docker_service, container in (compose["services"].items()):
            c = Container(docker_service, container, self.path)
            self.containers.append(c)

        if "networks" in compose.keys():
            for net_name, network in compose["networks"].items():
                if not network:
                    continue
                if "external" in network.keys():
                    self.networks.append(net_name)

    def setup(self):
        """
        Setup all services, meaning creating networks and ODI-managed volumes. ODI-managed volumes are those in /tmp or
        in the folder <odi_path>/<service>/volumes/<my_volume>. Read-only volumes are also regarded as not ODI-managed
        :return:
        """
        rich.print(f"   setting up service '{self.name}'")
        dclient = docker.from_env()
        existing_networks = [n.name for n in dclient.networks.list()]
        for network in self.networks:
            if network not in existing_networks:
                rich.print(f"    Creating network {network}")
                dclient.networks.create(network)
            else:
                rich.print(f"    [grey42]Network {network} already exists")

        for c in self.containers:
            c.setup()

        for path, user in self.force_ownerships.items():
            rich.print(f"    Forcing ownership of '{path}' to user '{user}'")
            run_subprocess(f"sudo chown {user}:{user} {path}")

    def build(self):
        for c in self.containers:
            c.build()

    def remove(self):
        for c in self.containers:
            c.remove()


class Infrastructure:
    def __init__(self, file):
        """
        High-level class to manage ODI deployments
        :param file: infrastructure.yaml file
        """
        with open(file) as f:
            conf = yaml.safe_load(f)["infrastructure"]

        self.conf = conf
        self.hostname = os.uname().nodename

        required_keys = {"path": str, "networks": dict, "port_mappings": dict, "services": dict, "soft_links": dict}
        check_required_keys(conf, required_keys)
        self.networks = {}
        self.servers = {}
        self.odi_services = {}
        self.all_odi_services = {}  # services including services to run in other servers
        self.mappings = {}
        self.soft_links = {}
        self.volumes = {}  # {"service_name": {src:"", dest: "", perms: "", user_id:""}}
        self.path = conf["path"]
        self.dcompose_services = {}
        self.dns = {}

        self.service_alias = {}  # key alias, value service name (the real one)

        # Make sure that the path exists
        path = conf["path"]

        self.odi_config = os.path.join(path, ".stat.json")

        if not os.path.isdir(path):
            ValueError(f"Path {path} does not exist")

        # Check the network
        for net_name, network in conf["networks"].items():
            net_ips = []
            self.networks[net_name] = network
            for server_name, server_conf in network.items():
                self.servers[server_name] = server_conf
                check_required_keys(server_conf, {"ip": str})
                check_optional_keys(server_conf, {"ip": str, "dns": list})

                if server_conf["ip"] in net_ips:
                    raise ValueError(f"Duplicated IP address '{server_conf['ip']}' in network '{net_name}'")
                net_ips.append(server_conf["ip"])

                if "dns" in server_conf.keys():
                    for dns in server_conf["dns"]:
                        if net_name not in self.dns.keys():
                            self.dns[net_name] = []
                        self.dns[net_name].append(dns)

        # Process port mappings #
        if conf["port_mappings"]:
            for srv_name, mappings in conf["port_mappings"].items():
                if srv_name not in self.servers.keys():
                    raise ValueError(f"server {srv_name} not declared in networks")

                self.mappings[srv_name] = []

                for mapping in mappings:
                    try:
                        protocol, src_port, dest_host, dest_port = mapping.split(":")
                    except ValueError:
                        raise SyntaxError(
                            f"syntax error in line {mapping} expected  [protocol]:[source port]:[destination address]:[destination port]")
                    assert int(src_port) > 0
                    assert int(dest_port) > 0
                    assert dest_host in self.servers.keys()
                    assert protocol in ["tcp", "udp"]

                    self.mappings[srv_name].append({
                        "protocol": protocol,
                        "src_port": src_port,
                        "dst_host": dest_host,
                        "dst_port": dest_port,
                    })

        # Process services
        service_dirs = [d for d in os.listdir(self.path) if os.path.isdir(os.path.join(self.path, d))]
        for service_name, service_conf in conf["services"].items():
            check_required_keys(service_conf, {"host": str})
            check_optional_keys(service_conf, {"host": str, "dns": str, "port": int, "force_ownership": list})

            local_service = False

            if service_conf["host"] == self.hostname:
                if service_name in service_dirs:
                    local_service = True
                else:
                    # If there is not a folder, maybe it's a link, e.g. "proxy-net1" should be a link to "proxy" service
                    for directory in service_dirs:
                        if service_name.startswith(directory):
                            # Register the service alias
                            self.service_alias[service_name] = directory
                            local_service = True

            force_ownerships = {}
            if "force_ownership" in service_conf.keys():
                for a in service_conf["force_ownership"]:
                    path, user = a.split(":")
                    if path.startswith("./"):
                        path = path[2:]
                    path = os.path.join(self.path, service_name, path)
                    force_ownerships[path] = user

            if local_service:
                s = Service(os.path.join(self.path, service_name), force_ownerships=force_ownerships)
                self.dcompose_services[service_name] = s
                self.odi_services[service_name] = service_conf
            else:
                pass
            self.all_odi_services[service_name] = service_conf


        # Process SoftLinks
        assert type(conf["soft_links"]) is dict, f"expected dict got {type(conf['soft_links'])}"
        for server, link_list in conf["soft_links"].items():
            assert server in self.servers.keys(), f"host '{server}' not registered"
            assert type(link_list) is list, f"LinkList for server '{server}' type={type(link_list)} expected list"
            for link in link_list:
                src, dst = link.split(":")  # make sure we have src and dst
                if server not in self.soft_links.keys():
                    self.soft_links[server] = []
                self.soft_links[server].append((src, dst))

        # self.docker = docker.from_env()

    def __repr__(self):
        repr = ""
        repr += "== Services ==\n"

        for name, service in self.services.items():
            repr += f"  {name}\n"
            for key, value in service.items():
                repr += f"    - {key}: {value}\n"
        return repr

    def get_host_network(self, target_host: str) -> (str, dict):
        """
        Get the network configuration for a specific host.
        :param target_host: hostname
        :return: network name for target_host
        :param target_host:
        :return: tuple (network_name, network_conf)
        """
        for network_name, network_conf in self.networks.items():
            for host in network_conf.keys():
                if host == target_host:
                    return network_name, network_conf
        raise LookupError(f"network for {target_host} not found")

    def ip_from_host(self, target_host):
        """
        takes a hostname and retunrs it's IP
        :param name:
        :return:
        """
        # First get the current network
        assert type(target_host) is str, f"Expected str got {type(target_host)}"

        _, current_network = self.get_host_network(self.hostname)

        if target_host == self.hostname:
            # If same machine, use the docker parent IP
            return "172.17.0.1"

        # Now that we have the network, check if current host and target_host are in the same network
        if target_host in current_network.keys() and self.hostname in current_network.keys():
            return current_network[target_host]["ip"]
        else:
            rich.print(f"[yellow]Error while trying to resolve '{target_host}' from '{self.hostname}' point of view")
            raise ValueError("Resolving hosts from different networks not yet implemented!")

    def create_port_mappings(self):
        """
        Creates port mapping in the machine
        """
        if self.hostname not in self.mappings.keys():
            rich.print(f"[grey42]No mapping for host '{self.hostname}'")
            return None

        # Check that all
        for m in self.mappings[self.hostname]:
            script = os.path.join(self.path, "scripts", "add_nat_rule.sh")
            dst_ip = self.ip_from_host(m["dst_host"])
            cmd = f"sudo {script} {m['src_port']} '{dst_ip}' {m['dst_port']} {m['protocol']}"
            rich.print(f"  calling external iptables handler: {cmd}")
            # Run script as a subprocess
            run_subprocess(cmd, allow_fail=False)

    def create_odi_env_file(self):
        """
        Creates the odi.env file where the ports and IPs are defined
        :return:
        """
        rich.print("Generating odi.env file...")
        lines = [
            f"#!/bin/bash\n",
            f"# ============================================ #\n",
            f"#     Open Data Infrastructure config file     #\n",
            f"# ============================================ #\n",
            f"# This file has been autogenerated from 'odi setup', please do not edit\n\n",
            f"# ODI Services IPs and ports\n"
        ]

        for service_name, service_conf in self.odi_services.items():
            try:
                if service_name.startswith("proxy"):
                    rich.print(f"[grey42]    skipping proxy service {service_name}'")
                    continue
                rich.print(f"    adding service: '{service_name}'")
                ip = self.ip_from_host(service_conf["host"])
                port = service_conf["port"]
                name = service_name.upper().replace("-", "_")
                lines.append("\n")
                lines.append(f"# Network config for ODI service {name}\n")
                lines.append(f"ODI_{name}_IP={ip}\n")
                lines.append(f"ODI_{name}_PORT={port}\n")

            except ValueError:
                rich.print(f"[red]Error processing service {service_name}")
                continue

        lines.append(f"\n#ODI Domain Name services\n")
        for service_name, service_conf in self.all_odi_services.items():
            # Now add only the DNS
            if "dns" in service_conf.keys():
                name = service_name.upper().replace("-", "_")
                lines.append(f"ODI_{name}_DNS={service_conf['dns']}\n")

        odi_env_file = os.path.join(self.path, "odi.env")
        with open(odi_env_file, "w") as f:
            f.writelines(lines)

        with open(odi_env_file, "w") as f:
            f.writelines(lines)

        # Now add this to ~/.bashrc
        odi_env = os.path.join(self.path, "odi.env")
        secrets_env = os.path.join(self.path, "secrets.env")
        magic_lines = f"\n\n# Load and export ODI env variables\n"
        magic_lines += f"export $(grep -v '^#' {odi_env} | xargs -0)\n"
        magic_lines += f"export $(grep -v '^#' {secrets_env} | xargs -0)\n"

        bash_rc_file = f"/home/{getpass.getuser()}/.bashrc"
        with open(bash_rc_file) as f:
            contents = f.read()
        if magic_lines not in contents:
            rich.print(f"[green] adding {magic_lines} to odi.env")
            with open(bash_rc_file, "a") as f:
                f.write(magic_lines)

    def create_nginx_conf(self):
        """
        Creates the file nginx.conf
        :return:
        """
        proxy_instance = ""
        # Get proxy instances that run on this machine
        for service_name, service_conf in self.all_odi_services.items():
            if service_conf["host"] == self.hostname and service_name.startswith("proxy"):
                proxy_instance = service_name

        if not proxy_instance:
            rich.print(f"[grey42]No proxies to be configured for host '{self.hostname}'")
            return

        rich.print(f"[cyan]Creating nginx config")
        dns = {
            # Dict where keys are dns names and values are a list of service names
        }

        current_network_name, _ = self.get_host_network(self.hostname)
        rich.print(f"Current network name: '{current_network_name}' ")
        for service_name, service_conf in self.all_odi_services.items():

            # Skip all services that are not running on this machine or that do not have a DNS
            service_host = service_conf["host"]
            net_name, _ = self.get_host_network(service_host)

            if "dns" in service_conf.keys() and service_conf["dns"] not in self.dns[net_name]:
                raise ValueError(f"Error in service {service_name}, DNS '{service_conf['dns']}' not declared in"
                                 f" network '{net_name}'")

            if current_network_name != net_name or "dns" not in service_conf.keys():
                rich.print(f"[grey42]    skipping {service_name}")
                continue

            dns_name = service_conf["dns"]
            if dns_name not in dns.keys():
                dns[dns_name] = [service_name]
            else:
                dns[dns_name].append(service_name)

        contents = nginx_conf_start

        # Then configure the rest of the services
        for dns, services in dns.items():
            contents += nginx_server_start.format(dns=dns)
            for service_name in services:
                service = self.all_odi_services[service_name]

                if service_name.startswith("proxy"):
                    # For the proxy configure only the GoAcess report
                    service_conf = service_nginx_config("goaccess").format()
                else:
                    # For the rest of the services specify port and ip
                    port = service["port"]
                    hostname = service["host"]
                    ip = self.ip_from_host(hostname)  # get the IP address from the proxy point of view
                    service_conf = service_nginx_config(service_name).format(port=port, ip=ip)
                contents += service_conf

            contents += nginx_server_end  # add finishing block for server
        contents += nginx_conf_end  # add finishing block for overall configuration file

        # now let's create the nginx.conf
        nginx_file = os.path.join(self.path, proxy_instance, "nginx.conf")
        with open(nginx_file, "w") as f:
            f.write(contents)
        rich.print(f"{nginx_file} for proxy {proxy_instance} created!")

    def create_soft_links(self):
        """
        Creates softlinks using ln -s command
        """
        rich.print("Creating soft links...")
        if self.hostname in self.soft_links.keys():
            rich.print("Creating soft links")
            links = self.soft_links[self.hostname]
            for src, dst in links:
                if os.path.exists(src):
                    rich.print(f"[grey42]    link {src}->{dst} already exists")
                else:
                    run_subprocess(f"sudo ln -s {dst} {src}")
                    rich.print(f"   creating link {src}->{dst}")

        for alias, dst in self.service_alias.items():
            # create a link
            alias = os.path.join(self.path, alias)
            if not os.path.exists(alias):
                dest = os.path.join(self.path, dst)
                rich.print(f"   creating link {alias}->{dest}")
                run_subprocess(f"ln -s {dest} {alias}")
            else:
                rich.print(f"[grey42]    link {alias}->{dst} already exists")

    def setup(self):
        rich.print("Setting up Infrastructure:")
        self.create_port_mappings()
        self.create_odi_env_file()
        self.create_nginx_conf()

        rich.print("Setting up Services:")
        for s in self.dcompose_services.values():
            s.setup()

        self.create_soft_links()



    def setup_service(self, service):
        """
        Setup only one service
        :param service:
        :return:
        """
        self.dcompose_services[service].setup()

    def remove_service(self, service):
        """
        Setup only one service
        :param service:
        :return:
        """
        self.dcompose_services[service].remove()

    def build_containers(self, service):
        """
        Builds container (only if the build clause in their docker-compose descriptions)
        :param service:
        :return:
        """
        self.dcompose_services[service].build()

    def remove(self, service_name):
        service = self.dcompose_services[service_name]
        service.remove()
