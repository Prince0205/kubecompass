from kubernetes import client

def provision_namespace(api, rbac, name, owner, cpu, memory):
    # 1. Namespace
    api.create_namespace(
        client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=name,
                labels={"owner": owner}
            )
        )
    )
    
    # 2. ResourceQuota
    quota = client.V1ResourceQuota(
        metadata=client.V1ObjectMeta(name="default-quota"),
        spec=client.V1ResourceQuotaSpec(
            hard={
                "requests.cpu": cpu,
                "requests.memory": memory,
                "limits.cpu": cpu,
                "limits.memory": memory
            }
        )
    )
    api.create_namespaced_resource_quota(name, quota)

    # 3. Role (namespace-scoped)
    role = client.V1Role(
        metadata=client.V1ObjectMeta(name="namespace-editor"),
        rules=[
            client.V1PolicyRule(
                api_groups=["", "apps", "extensions"],
                resources=["*"],
                verbs=["get", "list", "watch", "create", "update", "delete"]
            )
        ]
    )
    rbac.create_namespaced_role(name, role)

    # 4. RoleBinding
    binding = client.V1RoleBinding(
        metadata=client.V1ObjectMeta(name="namespace-editor-binding"),
        subjects=[
            client.V1Subject(
                kind="User",
                name=owner
            )
        ],
        role_ref=client.V1RoleRef(
            kind="Role",
            name="namespace-editor",
            api_group="rbac.authorization.k8s.io"
        )
    )
    rbac.create_namespaced_role_binding(name, binding)

    # 5. LimitRange
    api.create_namespaced_limit_range(name, limit_range)

def create_limit_range(api, namespace):
    limit_range = client.V1LimitRange(
        metadata=client.V1ObjectMeta(name="default-limits"),
        spec=client.V1LimitRangeSpec(
            limits=[
                client.V1LimitRangeItem(
                    type="Container",
                    default={
                        "cpu": "500m",
                        "memory": "512Mi"
                    },
                    default_request={
                        "cpu": "250m",
                        "memory": "256Mi"
                    }
                )
            ]
        )
    )
    
