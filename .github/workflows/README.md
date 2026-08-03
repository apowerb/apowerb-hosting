# Release publishing workflow

This workflow publishes the Helm chart as an OCI artifact during a GitHub Release.

## Registry targets

- Docker Hub: https://hub.docker.com/r/apowerb/apowerb
- GitHub Container Registry: https://github.com/orgs/apowerb/packages

## Required secrets

- `DOCKERHUB_USERNAME`
- `DOCKERHUB_TOKEN`

## Release trigger

The workflow is intended to run on a GitHub Release event.

## Result

The same packaged chart is pushed to both the Docker Hub OCI registry and the GitHub Container Registry OCI endpoint.
