#!/usr/bin/env python3
"""
Controls the execution of the ODI services

author: Enoc Martínez
institution: Universitat Politècnica de Catalunya (UPC)
email: enoc.martinez@upc.edu
license: MIT
created: 5/11/23
"""
from scripts.infrastructure import Infrastructure
import dotenv
from argparse import ArgumentParser
import os
import rich
from scripts.utils import run_subprocess_pipe

verbose = False


def debug(anything: any):
    if verbose:
        rich.print(f"[grey42]{anything}")


def info(anything: any):
    rich.print(f"{anything}")


def warning(msg: any):
    rich.print(f"[yellow]WARNING: {msg}")


def error(msg: any, exc=False):
    rich.print(f"[red]ERROR: {msg}")
    if exc:
        exit(-1)


if __name__ == "__main__":

    valid_options = ["up", "down", "start", "stop", "setup", "logs", "list", "remove", "logs"]

    argparser = ArgumentParser()
    argparser.add_argument("-i", "--infrastructure", help="Path no infrastructure.yaml", type=str,
                           default="/opt/odi/infrastructure.yaml")
    argparser.add_argument("action", help=f"Docker action ({' / '.join(valid_options)})", type=str)
    argparser.add_argument("services", help="service to list", type=str, nargs="*")
    argparser.add_argument("-v", "--verbose", help="verbose output", action="store_true")
    args = argparser.parse_args()

    if args.verbose:
        verbose = True

    debug("Loading infrastructure file...")
    infrastructure = Infrastructure(args.infrastructure)
    debug("Loading odi.env file...")
    dotenv.load_dotenv(os.path.join(infrastructure.path, "odi.env"))
    debug("Loading passwords.env file...")
    dotenv.load_dotenv(os.path.join(infrastructure.path, "secrets.env"))

    # if no services, apply the action to all of them
    valid_services = infrastructure.dcompose_services.keys()

    if "list" == args.action:
        rich.print(f"Valid services for host '{infrastructure.hostname}': {', '.join(valid_services)}")
        rich.print(f"Valid actions: {', '.join(valid_options)}")
        exit()

    services = args.services
    if services:
        for s in services:
            if s not in valid_services:
                error(f"Service '{s}' not in valid services: {', '.join(valid_services)}", exc=True)

    if args.action == "setup" and len(services) == 0:
        infrastructure.setup()
        exit(0)

    if not args.services:
        services = valid_services
    else:
        pass

    if args.action not in valid_options:
        error(f"ERROR: action '{args.action}' no tin valid options: {', '.join(valid_options)}", exc=True)

    oldpath = os.getcwd()
    for service in services:
        # move to service

        newpath = os.path.join(infrastructure.path, service)
        debug(f"Changing current dir to {newpath}")
        os.chdir(newpath)

        if args.action == "up":
            infrastructure.build_containers(service)
            info(f"running docker compose up for '{service}'    ")
            run_subprocess_pipe("docker compose up -d", debug=verbose)

        elif args.action == "down":
            info(f"running docker compose down for '{service}'")
            run_subprocess_pipe("docker compose down", debug=verbose)

        elif args.action == "start":
            info(f"running docker start down for '{service}'")
            run_subprocess_pipe("docker compose start", debug=verbose)

        elif args.action == "stop":
            info(f"running docker stop down for '{service}'")
            run_subprocess_pipe("docker compose stop", debug=verbose)

        elif args.action == "setup":
            info(f"Setup service '{service}'")
            infrastructure.setup_service(service)

        elif args.action == "logs":
            info(f"Showing docker logs for service '{service}'")
            run_subprocess_pipe("docker compose logs", debug=verbose)

        elif args.action == "remove":
            info(f"running docker compose down for '{service}'")
            run_subprocess_pipe("docker compose down", debug=verbose)
            infrastructure.remove_service(service)
        else:
            raise ValueError(f"Action {args.action} not implemented!")

    # back to old path
    os.chdir(oldpath)
    rich.print("[green]done!")


