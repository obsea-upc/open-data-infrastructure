#!/bin/bash

echo "Getting CKAN's api key in a quick and dirty way"
docker exec ckan ckan user token add ckan_admin tk1 | tail -n 1 | sed 's/\t//g'