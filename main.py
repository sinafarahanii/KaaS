import os
from kubernetes import client, config
from kubernetes.client.rest import ApiException
from fastapi import FastAPI, HTTPException, Depends, Request, Response
from pydantic import BaseModel
from datetime import datetime
import asyncpg
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from models import Health
from db import engine, connect_to_db
from prometheus_client import Counter, Histogram, generate_latest
import time


app = FastAPI()
# Load kube config
config.load_kube_config()

# Create a client
apps_v1 = client.AppsV1Api()
core_v1 = client.CoreV1Api()

REQUEST_COUNT = Counter("request_count", "Total number of requests")
FAILED_REQUEST_COUNT = Counter("failed_request_count", "Total number of failed requests")
REQUEST_LATENCY = Histogram("request_latency_seconds", "Latency of HTTP requests in seconds")
DB_ERROR_COUNT = Counter("db_error_count", "Total number of database errors")
DB_RESPONSE_LATENCY = Histogram("db_response_latency_seconds", "Latency of database responses in seconds")

class ApplicationConfig(BaseModel):
    app_name: str
    replicas: int
    user: str
    password: str
    db_name: str
    image_address: str
    image_tag: str
    domain_address: str
    service_port: int
    external_access: bool
    monitor: bool
    cpu_request: str
    cpu_limit: str
    memory_request: str
    memory_limit: str


class ResourceUpdateConfig(BaseModel):
    app_name: str
    cpu_request: str
    cpu_limit: str
    memory_request: str
    memory_limit: str


@app.post("/deploy-application")
def deploy_postgresql(config: ApplicationConfig):
    app_name = config.app_name
    replicas = config.replicas
    user = config.user
    password = config.password
    db_name = config.db_name
    image_address = config.image_address
    image_tag = config.image_tag
    domain_address = config.domain_address
    service_port = config.service_port
    external_access = config.external_access
    monitor = config.monitor
    cpu_request = config.cpu_request
    cpu_limit = config.cpu_limit
    memory_request = config.memory_request
    memory_limit = config.memory_limit

    api_instance = client.CoreV1Api()
    apps_v1_api = client.AppsV1Api()
    networking_v1_api = client.NetworkingV1Api()

    try:
        stateful_set = apps_v1_api.read_namespaced_stateful_set(name=f"{app_name}-statefulset", namespace="default")
        stateful_set.spec.template.spec.containers[0].resources = client.V1ResourceRequirements(
            requests={"cpu": cpu_request, "memory": memory_request},
            limits={"cpu": cpu_limit, "memory": memory_limit}
        )
        apps_v1_api.replace_namespaced_stateful_set(name=f"{app_name}-statefulset", namespace="default",
                                                    body=stateful_set)
        return {"message": f"Resources for {app_name} updated successfully"}
    except client.exceptions.ApiException as e:
        if e.status == 404:

            secret = client.V1Secret(
                metadata=client.V1ObjectMeta(name=f"{app_name}-secret"),
                type="Opaque",
                string_data={
                    "DB_USER": user,
                    "DB_PASSWORD": password,
                    "DB_NAME": db_name,
                }
            )

            config_map = client.V1ConfigMap(
                metadata=client.V1ObjectMeta(name=f"{app_name}-config"),
                data={
                    "DB_USER": user,
                    "DB_PASSWORD": password,
                    "DB_NAME": db_name,
                }
            )

            stateful_set = client.V1StatefulSet(
                metadata=client.V1ObjectMeta(name=f"{app_name}-statefulset"),
                spec=client.V1StatefulSetSpec(
                    replicas=replicas,
                    selector=client.V1LabelSelector(
                        match_labels={"app": app_name,
                                      'monitor': 'true' if monitor else 'false'}
                    ),
                    service_name=f"{app_name}-service",
                    template=client.V1PodTemplateSpec(
                        metadata=client.V1ObjectMeta(labels={"app": app_name,
                                                             'monitor': 'true' if monitor else 'false'}),
                        spec=client.V1PodSpec(containers=[
                            client.V1Container(
                                name=f"{app_name}-container",
                                image=f"{image_address}:{image_tag}",
                                env=[
                                    client.V1EnvVar(
                                        name="DB_USER",
                                        value_from=client.V1EnvVarSource(
                                            secret_key_ref=client.V1SecretKeySelector(
                                                name=f"{app_name}-secret",
                                                key="DB_USER"
                                            )
                                        )
                                    ),
                                    client.V1EnvVar(
                                        name="POSTGRES_PASSWORD",
                                        value_from=client.V1EnvVarSource(
                                            secret_key_ref=client.V1SecretKeySelector(
                                                name=f"{app_name}-secret",
                                                key="DB_PASSWORD"
                                            )
                                        )
                                    ),
                                    client.V1EnvVar(
                                        name="DB_NAME",
                                        value_from=client.V1EnvVarSource(
                                            secret_key_ref=client.V1SecretKeySelector(
                                                name=f"{app_name}-secret",
                                                key="DB_NAME"
                                            )
                                        )
                                    )
                                ],
                                ports=[client.V1ContainerPort(container_port=service_port)]
                            )
                        ])
                    )
                )
            )

            service = client.V1Service(
                metadata=client.V1ObjectMeta(name=f"{app_name}-service"),
                spec=client.V1ServiceSpec(
                    selector={"app": app_name},
                    ports=[client.V1ServicePort(port=service_port, target_port=service_port)],
                    type="LoadBalancer" if external_access else "ClusterIP"
                )
            )
            ingress = client.V1Ingress(
                metadata=client.V1ObjectMeta(name=f"{app_name}-ingress"),
                spec=client.V1IngressSpec(
                    rules=[
                        client.V1IngressRule(
                            host=domain_address,
                            http=client.V1HTTPIngressRuleValue(
                                paths=[
                                    client.V1HTTPIngressPath(
                                        path="/",
                                        path_type="Prefix",
                                        backend=client.V1IngressBackend(
                                            service=client.V1IngressServiceBackend(
                                                name=f"{app_name}-service",
                                                port=client.V1ServiceBackendPort(number=service_port)
                                            )
                                        )
                                    )
                                ]
                            )
                        )
                    ]
                )
            )


            try:
                api_instance.create_namespaced_secret(
                    namespace="default",
                    body=secret
                )

                api_instance.create_namespaced_config_map(
                    namespace="default",
                    body=config_map
                )

                apps_v1_api.create_namespaced_stateful_set(
                    namespace="default",
                    body=stateful_set
                )

                api_instance.create_namespaced_service(
                    namespace="default",
                    body=service
                )
                if external_access:
                    networking_v1_api.create_namespaced_ingress(
                        namespace="default",
                        body=ingress
                    )
            except client.exceptions.ApiException as e:
                raise HTTPException(status_code=400, detail=str(e))

    return {"message": f"Application deployment for {app_name} created successfully"}


@app.post("/update-resources")
def update_resources(config: ResourceUpdateConfig):
    app_name = config.app_name
    cpu_request = config.cpu_request
    cpu_limit = config.cpu_limit
    memory_request = config.memory_request
    memory_limit = config.memory_limit

    apps_v1_api = client.AppsV1Api()
    try:
        stateful_set = apps_v1_api.read_namespaced_stateful_set(name=f"{app_name}-statefulset", namespace="default")

        stateful_set.spec.template.spec.containers[0].resources = client.V1ResourceRequirements(
            requests={"cpu": cpu_request, "memory": memory_request},
            limits={"cpu": cpu_limit, "memory": memory_limit}
        )

        apps_v1_api.replace_namespaced_stateful_set(name=f"{app_name}-statefulset", namespace="default",
                                                    body=stateful_set)

    except client.exceptions.ApiException as e:
        if e.status == 404:
            raise HTTPException(status_code=404, detail=f"StatefulSet for {app_name} not found")
        else:
            raise HTTPException(status_code=400, detail=str(e))

    return {"message": f"Resources for {app_name} updated successfully"}


@app.get("/status/{app_name}")
def get_app_status(app_name):

    try:
        # Get the deployment
        deployment = apps_v1.read_namespaced_stateful_set(name=f'{app_name}-statefulset', namespace="default")

        # Extract deployment information
        deployment_name = deployment.metadata.name
        replicas = deployment.spec.replicas
        ready_replicas = deployment.status.ready_replicas

        # Get pods related to the deployment
        pod_list = core_v1.list_namespaced_pod(namespace="default", label_selector=f"app={app_name}")
        # Extract pod information
        pod_statuses = []
        for pod in pod_list.items:
            pod_status = {
                "Name": pod.metadata.name,
                "Phase": pod.status.phase,
                "HostIP": pod.status.host_ip,
                "PodIP": pod.status.pod_ip,
                "StartTime": pod.status.start_time.strftime('%Y-%m-%d %H:%M:%S') if pod.status.start_time else None
            }
            pod_statuses.append(pod_status)

        # Build the response
        response = {
            "DeploymentName": deployment_name,
            "Replicas": replicas,
            "ReadyReplicas": ready_replicas,
            "PodStatuses": pod_statuses
        }

        return response

    except ApiException as e:
        if e.status == 404:
            return {"error": "Deployment not found"}
        else:
            return {"error": str(e)}


@app.get("/status/")
def get_all_status():
    try:
        # Get all deployments
        deployments = apps_v1.list_namespaced_stateful_set(namespace="default")

        all_apps_status = []

        for deployment in deployments.items:
            # Extract deployment information
            deployment_name = deployment.metadata.name.split('-')
            deployment_name.pop(-1)
            name = ''
            for item in deployment_name:
                name += item + '-'
            deployment_name = name[:-1]
            print(deployment_name)
            replicas = deployment.spec.replicas
            ready_replicas = deployment.status.ready_replicas

            # Get pods related to the deployment
            pod_list = core_v1.list_namespaced_pod(namespace="default", label_selector=f"app={deployment_name}")

            # Extract pod information
            pod_statuses = []
            for pod in pod_list.items:
                pod_status = {
                    "Name": pod.metadata.name,
                    "Phase": pod.status.phase,
                    "HostIP": pod.status.host_ip,
                    "PodIP": pod.status.pod_ip,
                    "StartTime": pod.status.start_time.strftime('%Y-%m-%d %H:%M:%S') if pod.status.start_time else None
                }
                pod_statuses.append(pod_status)

            # Build the deployment status
            deployment_status = {
                "DeploymentName": deployment_name,
                "Replicas": replicas,
                "ReadyReplicas": ready_replicas,
                "PodStatuses": pod_statuses
            }

            all_apps_status.append(deployment_status)

        return all_apps_status

    except ApiException as e:
        return {"error": str(e)}


@app.get('/health')
def get_health():
    deployments = apps_v1.list_namespaced_stateful_set(namespace="default")
    monitored = []
    for dp in deployments.items:
        labels = dp.spec.selector.match_labels
        try:
            should_monitor = labels['monitor']
            if should_monitor:
                monitored.append(dp)
        except Exception as e:
            continue
    for deployment in monitored:
        deployment_name = deployment.metadata.name.split('-')
        deployment_name.pop(-1)
        name = ''
        for item in deployment_name:
            name += item + '-'
        app_name = name[:-1]
        created_at = deployment.status.start_time.strftime('%Y-%m-%d %H:%M:%S')

        replicas = deployment.spec.replicas
        ready_replicas = deployment.status.ready_replicas
        if replicas != ready_replicas:
            raise HTTPException(400, detail=f"{app_name},{created_at}")

        deployment_status = {
            "app_name": app_name,
            "created_at": created_at,
        }
        return deployment_status


@app.get('/health/{app_name}')
def get_health_status(app_name, db: Session = Depends(connect_to_db)):
    record = db.query(Health).filter(Health.app_name == app_name).first()
    if record:
        return record
    else:
        raise HTTPException(status_code=404, detail=f"Application {app_name} not found")


is_database_connected = True
is_service_ready = True
is_service_healthy = True
is_service_started = True


@app.get("/ready")
def readiness_probe():

    if is_service_ready and is_database_connected:
        return {"status": "ready"}
    else:
        raise HTTPException(status_code=503, detail="Service not ready")


@app.get("/healthz")
def liveness_probe():

    if is_service_healthy:
        return {"status": "healthy"}
    else:
        raise HTTPException(status_code=500, detail="Service not healthy")


@app.get("/start")
def startup_probe():

    if is_service_started:
        return {"status": "started"}
    else:
        raise HTTPException(status_code=500, detail="Service not started")


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    REQUEST_COUNT.inc()
    start_time = time.time()
    try:
        response = await call_next(request)
        if response.status_code >= 400:
            FAILED_REQUEST_COUNT.inc()
        return response
    except Exception as e:
        FAILED_REQUEST_COUNT.inc()
        raise e
    finally:
        duration = time.time() - start_time
        REQUEST_LATENCY.observe(duration)


@app.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type="text/plain")


@app.get("/example")
async def example():
    start_time = time.time()
    try:

        db_response_time = simulate_db_request()
        DB_RESPONSE_LATENCY.observe(db_response_time)
        return {"message": "success"}
    except Exception as e:
        DB_ERROR_COUNT.inc()
        raise e


def simulate_db_request():

    time.sleep(0.1)
    return 0.1





