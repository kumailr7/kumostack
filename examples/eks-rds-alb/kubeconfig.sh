#!/usr/bin/env bash
# kubeconfig.sh — Generate kubectl context for the KumoStack EKS cluster
#
# Usage:
#   bash kubeconfig.sh            # merges 'kumostack' context into ~/.kube/config
#   bash kubeconfig.sh --print    # prints kubeconfig YAML to stdout
#
# After running: kubectl --context=kumostack get nodes
set -euo pipefail

CONTEXT_NAME="kumostack"
TF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Reading Terraform outputs from $TF_DIR …"
cd "$TF_DIR"

CLUSTER=$(terraform output -raw eks_cluster_name 2>/dev/null)

if [[ -z "$CLUSTER" || "$CLUSTER" == *"No outputs"* ]]; then
  echo "ERROR: No Terraform outputs found. Run 'terraform apply' first."
  exit 1
fi

CONTAINER="kumostack-eks-${CLUSTER}"

# Get host-mapped port for the k3s API server
HOST_PORT=$(docker port "$CONTAINER" 6443 2>/dev/null | grep -oP ':\K[0-9]+' | head -1)
if [[ -z "$HOST_PORT" ]]; then
  echo "ERROR: Container '$CONTAINER' is not running. Run 'terraform apply' first."
  exit 1
fi

ENDPOINT="https://localhost:${HOST_PORT}"
echo "  Cluster:   $CLUSTER"
echo "  Container: $CONTAINER"
echo "  Endpoint:  $ENDPOINT"

# Pull the real kubeconfig from the k3s container and patch the server URL
RAW_KUBECONFIG=$(docker exec "$CONTAINER" cat /etc/rancher/k3s/k3s.yaml 2>/dev/null)
if [[ -z "$RAW_KUBECONFIG" ]]; then
  echo "ERROR: Could not read kubeconfig from container. Is k3s ready?"
  exit 1
fi

# Replace the internal server URL with the host-accessible one
PATCHED=$(echo "$RAW_KUBECONFIG" | sed "s|server: https://127.0.0.1:6443|server: ${ENDPOINT}|g")

if [[ "${1:-}" == "--print" ]]; then
  echo "$PATCHED"
  exit 0
fi

# Write to a temp file and merge into ~/.kube/config
TMPFILE=$(mktemp /tmp/kumostack-kubeconfig-XXXXXX.yaml)
trap "rm -f $TMPFILE" EXIT
echo "$PATCHED" > "$TMPFILE"

# Rename default cluster/user/context to 'kumostack'
KUBECONFIG="$TMPFILE:${HOME}/.kube/config" kubectl config view --flatten > /tmp/merged-kubeconfig.yaml

# Extract the real CA, cert, key from the temp kubeconfig
CA_DATA=$(kubectl --kubeconfig="$TMPFILE" config view --raw -o jsonpath='{.clusters[0].cluster.certificate-authority-data}')
CERT_DATA=$(kubectl --kubeconfig="$TMPFILE" config view --raw -o jsonpath='{.users[0].user.client-certificate-data}')
KEY_DATA=$(kubectl --kubeconfig="$TMPFILE" config view --raw -o jsonpath='{.users[0].user.client-key-data}')

# Set cluster entry with the host-accessible endpoint
kubectl config set-cluster "$CONTEXT_NAME" \
  --server="$ENDPOINT" \
  --certificate-authority=<(echo "$CA_DATA" | base64 -d) \
  --embed-certs=true

# Set credentials using the real k3s client certificate
kubectl config set-credentials "$CONTEXT_NAME-admin" \
  --client-certificate=<(echo "$CERT_DATA" | base64 -d) \
  --client-key=<(echo "$KEY_DATA" | base64 -d) \
  --embed-certs=true

kubectl config set-context "$CONTEXT_NAME" \
  --cluster="$CONTEXT_NAME" \
  --user="$CONTEXT_NAME-admin" \
  --namespace="default"

kubectl config use-context "$CONTEXT_NAME"

# Detect the KumoStack container IP on kumostack_default so pods can reach it
KUMOSTACK_IP=$(docker inspect kumostack \
  --format '{{range $k,$v := .NetworkSettings.Networks}}{{if eq $k "kumostack_default"}}{{$v.IPAddress}}{{end}}{{end}}' 2>/dev/null || true)

if [[ -n "$KUMOSTACK_IP" ]]; then
  echo "  KumoStack IP on kumostack_default: $KUMOSTACK_IP"
  # Patch deployment.yaml hostAliases with the real IP (in-place, safe to re-run)
  DEPLOY_YAML="$TF_DIR/k8s/deployment.yaml"
  sed -i "s|^        - ip: \"[0-9.]*\"      # kumostack container IP|        - ip: \"$KUMOSTACK_IP\"      # kumostack container IP|" "$DEPLOY_YAML"
  echo "  Updated k8s/deployment.yaml hostAliases → $KUMOSTACK_IP"
fi

echo ""
echo "Done! Context '$CONTEXT_NAME' is now active."
echo ""
echo "  kubectl apply -f k8s/"
echo "  kubectl get nodes"
echo "  kubectl get namespaces"
