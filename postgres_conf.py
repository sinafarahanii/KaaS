from kubernetes import client, config
from fastapi import HTTPException
from kubernetes.client import ApiException

#from main import core_v1, apps_v1


config.load_incluster_config()

secret = client.V1Secret(
    metadata=client.V1ObjectMeta(name="postgresql-secret"),
    type="Opaque",
    string_data={
        "POSTGRESQL_USERNAME": "username",
        "POSTGRESQL_PASSWORD": "password",
        "POSTGRESQL_DATABASE": "health-check",
        "POSTGRESQL_REPLICATION_USER": "replication_user",
        "POSTGRESQL_REPLICATION_PASSWORD": "replication_password"
    }
)
config_map = client.V1ConfigMap(
    metadata=client.V1ObjectMeta(name="postgresql-config"),
    data={
        "POSTGRESQL_MASTER_HOST": "postgresql-master-service",
        "POSTGRESQL_SLAVE_HOST": "postgresql-slave-service",
    }
)
master_labels = {"app": "postgresql", "role": "master"}
master_stateful_set = client.V1StatefulSet(
    metadata=client.V1ObjectMeta(name="postgresql-master"),
    spec=client.V1StatefulSetSpec(
        replicas=1,
        selector=client.V1LabelSelector(match_labels=master_labels),
        service_name="postgresql-master-service",
        template=client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels=master_labels),
            spec=client.V1PodSpec(
                containers=[
                    client.V1Container(
                        name="postgresql-master-container",
                        image="bitnami/postgresql:latest",
                        env=[
                            client.V1EnvVar(
                                name="POSTGRESQL_USERNAME",
                                value_from=client.V1EnvVarSource(
                                    secret_key_ref=client.V1SecretKeySelector(
                                        name="postgresql-secret",
                                        key="POSTGRESQL_USERNAME"
                                    )
                                )
                            ),
                            client.V1EnvVar(
                                name="POSTGRESQL_PASSWORD",
                                value_from=client.V1EnvVarSource(
                                    secret_key_ref=client.V1SecretKeySelector(
                                        name="postgresql-secret",
                                        key="POSTGRESQL_PASSWORD"
                                    )
                                )
                            ),
                            client.V1EnvVar(
                                name="POSTGRESQL_DATABASE",
                                value_from=client.V1EnvVarSource(
                                    secret_key_ref=client.V1SecretKeySelector(
                                        name="postgresql-secret",
                                        key="POSTGRESQL_DATABASE"
                                    )
                                )
                            ),
                            client.V1EnvVar(
                                name="POSTGRESQL_REPLICATION_USER",
                                value_from=client.V1EnvVarSource(
                                    secret_key_ref=client.V1SecretKeySelector(
                                        name="postgresql-secret",
                                        key="POSTGRESQL_REPLICATION_USER"
                                    )
                                )
                            ),
                            client.V1EnvVar(
                                name="POSTGRESQL_REPLICATION_PASSWORD",
                                value_from=client.V1EnvVarSource(
                                    secret_key_ref=client.V1SecretKeySelector(
                                        name="postgresql-secret",
                                        key="POSTGRESQL_REPLICATION_PASSWORD"
                                    )
                                )
                            ),
                            client.V1EnvVar(
                                name="POSTGRESQL_REPLICATION_MODE",
                                value="master"
                            )
                        ],
                        ports=[client.V1ContainerPort(container_port=5432)],
                        resources=client.V1ResourceRequirements(
                            requests={"cpu": "500m", "memory": "512Mi"},
                            limits={"cpu": "1", "memory": "1Gi"}
                        ),
                        volume_mounts=[client.V1VolumeMount(
                            name="postgresql-master-pv",
                            mount_path="/bitnami/postgresql"
                        )]
                    )
                ],
                volumes=[
                    client.V1Volume(
                        name="postgresql-master-pv",
                        persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                            claim_name="postgresql-master-pvc"
                        )
                    )
                ]
            )
        )
    )
)
slave_labels = {"app": "postgresql", "role": "slave"}
slave_stateful_set = client.V1StatefulSet(
    metadata=client.V1ObjectMeta(name="postgresql-slave"),
    spec=client.V1StatefulSetSpec(
        replicas=1,
        selector=client.V1LabelSelector(match_labels=slave_labels),
        service_name="postgresql-slave-service",
        template=client.V1PodTemplateSpec(
            metadata=client.V1ObjectMeta(labels=slave_labels),
            spec=client.V1PodSpec(
                containers=[
                    client.V1Container(
                        name="postgresql-slave-container",
                        image="bitnami/postgresql:latest",
                        env=[
                            client.V1EnvVar(
                                name="POSTGRESQL_USERNAME",
                                value_from=client.V1EnvVarSource(
                                    secret_key_ref=client.V1SecretKeySelector(
                                        name="postgresql-secret",
                                        key="POSTGRESQL_USERNAME"
                                    )
                                )
                            ),
                            client.V1EnvVar(
                                name="POSTGRESQL_PASSWORD",
                                value_from=client.V1EnvVarSource(
                                    secret_key_ref=client.V1SecretKeySelector(
                                        name="postgresql-secret",
                                        key="POSTGRESQL_PASSWORD"
                                    )
                                )
                            ),
                            client.V1EnvVar(
                                name="POSTGRESQL_DATABASE",
                                value_from=client.V1EnvVarSource(
                                    secret_key_ref=client.V1SecretKeySelector(
                                        name="postgresql-secret",
                                        key="POSTGRESQL_DATABASE"
                                    )
                                )
                            ),
                            client.V1EnvVar(
                                name="POSTGRESQL_REPLICATION_USER",
                                value_from=client.V1EnvVarSource(
                                    secret_key_ref=client.V1SecretKeySelector(
                                        name="postgresql-secret",
                                        key="POSTGRESQL_REPLICATION_USER"
                                    )
                                )
                            ),
                            client.V1EnvVar(
                                name="POSTGRESQL_REPLICATION_PASSWORD",
                                value_from=client.V1EnvVarSource(
                                    secret_key_ref=client.V1SecretKeySelector(
                                        name="postgresql-secret",
                                        key="POSTGRESQL_REPLICATION_PASSWORD"
                                    )
                                )
                            ),
                            client.V1EnvVar(
                                name="POSTGRESQL_REPLICATION_MODE",
                                value="slave"
                            ),
                            client.V1EnvVar(
                                name="POSTGRESQL_MASTER_HOST",
                                value_from=client.V1EnvVarSource(
                                    config_map_key_ref=client.V1ConfigMapKeySelector(
                                        name="postgresql-config",
                                        key="POSTGRESQL_MASTER_HOST"
                                    )
                                )
                            )
                        ],
                        ports=[client.V1ContainerPort(container_port=5432)],
                        resources=client.V1ResourceRequirements(
                            requests={"cpu": "500m", "memory": "512Mi"},
                            limits={"cpu": "1", "memory": "1Gi"}
                        ),
                        volume_mounts=[client.V1VolumeMount(
                            name="postgresql-slave-pv",
                            mount_path="/bitnami/postgresql"
                        )]
                    )
                ],
                volumes=[
                    client.V1Volume(
                        name="postgresql-slave-pv",
                        persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                            claim_name="postgresql-slave-pvc"
                        )
                    )
                ]
            )
        )
    )
)
master_service = client.V1Service(
    metadata=client.V1ObjectMeta(name="postgresql-master-service"),
    spec=client.V1ServiceSpec(
        selector={"app": "postgresql", "role": "master"},
        ports=[client.V1ServicePort(port=5432, target_port=5432)],
        type="LoadBalancer"
    )
)

slave_service = client.V1Service(
    metadata=client.V1ObjectMeta(name="postgresql-slave-service"),
    spec=client.V1ServiceSpec(
        selector={"app": "postgresql", "role": "slave"},
        ports=[client.V1ServicePort(port=5433, target_port=5433)],
        type="LoadBalancer"
    )
)
master_pvc = client.V1PersistentVolumeClaim(
    metadata=client.V1ObjectMeta(name="postgresql-master-pvc"),
    spec=client.V1PersistentVolumeClaimSpec(
        access_modes=["ReadWriteOnce"],
        resources=client.V1ResourceRequirements(
            requests={"storage": "10Gi"}
        )
    )
)

slave_pvc = client.V1PersistentVolumeClaim(
    metadata=client.V1ObjectMeta(name="postgresql-slave-pvc"),
    spec=client.V1PersistentVolumeClaimSpec(
        access_modes=["ReadWriteOnce"],
        resources=client.V1ResourceRequirements(
            requests={"storage": "10Gi"}
        )
    )
)

apps_v1 = client.AppsV1Api()
core_v1 = client.CoreV1Api()
try:
    #core_v1.delete_namespaced_persistent_volume_claim(namespace="default", name=master_pvc.metadata.name)
    core_v1.read_namespaced_persistent_volume_claim(namespace="default", name=master_pvc.metadata.name)

except client.exceptions.ApiException as e:
    if e.status == 404:
        core_v1.create_namespaced_persistent_volume_claim(namespace="default", body=master_pvc)

try:
    #core_v1.delete_namespaced_persistent_volume_claim(namespace="default", name=slave_pvc.metadata.name)
    core_v1.read_namespaced_persistent_volume_claim(namespace="default", name=slave_pvc.metadata.name)

except client.exceptions.ApiException as e:
    if e.status == 404:
        core_v1.create_namespaced_persistent_volume_claim(namespace="default", body=slave_pvc)

try:
    #apps_v1.delete_namespaced_stateful_set(namespace="default", name=slave_stateful_set.metadata.name)
    apps_v1.read_namespaced_stateful_set(namespace="default", name=slave_stateful_set.metadata.name)


except client.exceptions.ApiException as e:
    if e.status == 404:
        apps_v1.create_namespaced_stateful_set(namespace="default", body=slave_stateful_set)


try:
    #apps_v1.delete_namespaced_stateful_set(namespace="default", name=master_stateful_set.metadata.name)
    apps_v1.read_namespaced_stateful_set(namespace="default", name=master_stateful_set.metadata.name)

except client.exceptions.ApiException as e:
    if e.status == 404:
        apps_v1.create_namespaced_stateful_set(namespace="default", body=master_stateful_set)

try:

    core_v1.delete_namespaced_service(namespace="default", name=slave_service.metadata.name)
    core_v1.read_namespaced_service(namespace="default", name=slave_service.metadata.name)

except client.exceptions.ApiException as e:
    if e.status == 404:
        core_v1.create_namespaced_service(namespace="default", body=slave_service)

try:

    core_v1.delete_namespaced_service(namespace="default", name=master_service.metadata.name)
    core_v1.read_namespaced_service(namespace="default", name=master_service.metadata.name)

except client.exceptions.ApiException as e:
    if e.status == 404:
        core_v1.create_namespaced_service(namespace="default", body=master_service)

try:
    core_v1.delete_namespaced_secret(namespace="default", name=secret.metadata.name)
    core_v1.create_namespaced_secret(namespace="default", body=secret)
    core_v1.delete_namespaced_config_map(namespace="default", name=config_map.metadata.name)
    core_v1.create_namespaced_config_map(namespace="default", body=config_map)

except client.exceptions.ApiException as e:
    raise HTTPException(status_code=400, detail=str(e))


