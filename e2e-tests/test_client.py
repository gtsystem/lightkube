import time
from datetime import datetime
from pathlib import Path
from string import ascii_lowercase
from random import choices

import pytest

from lightkube import Client, ApiError, AsyncClient
from lightkube.types import PatchType
from lightkube.resources.core_v1 import Pod, Node, ConfigMap, Service, Namespace
from lightkube.resources.apps_v1 import Deployment
from lightkube.models.meta_v1 import ObjectMeta
from lightkube.models.core_v1 import PodSpec, Container, ServiceSpec, ServicePort
from lightkube.codecs import load_all_yaml
from lightkube.generic_resource import create_namespaced_resource, get_generic_resource, \
    load_in_cluster_generic_resources, async_load_in_cluster_generic_resources

uid_count = 0


@pytest.fixture
def obj_name():
    global uid_count
    uid_count += 1
    return f'test-{datetime.utcnow().strftime("%Y%m%d%H%M%S")}-{uid_count}'


def names(obj_list):
    return [obj.metadata.name for obj in obj_list]


def create_pod(name, command) -> Pod:
    return Pod(
        metadata=ObjectMeta(name=name, labels={'app-name': name}),
        spec=PodSpec(containers=[Container(
            name='main',
            image='busybox',
            args=[
                "/bin/sh",
                "-c",
                command
            ],
        )], terminationGracePeriodSeconds=1)
    )


def wait_pod(client, pod):
    # watch pods
    for etype, pod in client.watch(Pod, labels={'app-name': pod.metadata.name},
                                   resource_version=pod.metadata.resourceVersion):
        if pod.status.phase != 'Pending':
            break


def test_pod_apis(obj_name):
    client = Client()

    # list kube-system namespace
    pods = [pod.metadata.name for pod in client.list(Pod, namespace='kube-system')]
    assert len(pods) > 0
    assert any(name.startswith('metrics-server') for name in pods)

    # create a pod
    pod = client.create(create_pod(obj_name, "while true;do echo 'this is a test';sleep 5; done"))
    try:
        assert pod.metadata.name == obj_name
        assert pod.metadata.namespace == client.namespace
        assert pod.status.phase


        wait_pod(client, pod)

        # read pod logs
        for l in client.log(obj_name, follow=True):
            assert l == 'this is a test\n'
            break
    finally:
        # delete the pod
        client.delete(Pod, obj_name)


def test_pod_not_exist():
    client = Client()
    with pytest.raises(ApiError) as exc_info:
        client.get(Pod, name='this-pod-is-not-found')

    status = exc_info.value.status
    assert status.code == 404
    assert status.details.name == 'this-pod-is-not-found'
    assert status.reason == 'NotFound'
    assert status.status == 'Failure'


def test_pod_already_exist(obj_name):
    client = Client()
    client.create(create_pod(obj_name, "sleep 5"))
    try:
        with pytest.raises(ApiError) as exc_info:
            client.create(create_pod(obj_name, "sleep 5"))
        status = exc_info.value.status
        assert status.code == 409
        assert status.reason == 'AlreadyExists'
        assert status.status == 'Failure'
    finally:
        # delete the pod
        client.delete(Pod, obj_name)


def test_global_methods():
    client = Client()
    nodes = [node.metadata.name for node in client.list(Node)]
    assert len(nodes) > 0
    node = client.get(Node, name=nodes[0])
    assert node.metadata.name == nodes[0]
    assert node.metadata.labels['kubernetes.io/os'] == node.status.nodeInfo.operatingSystem


def test_namespaced_methods(obj_name):
    client = Client()
    config = ConfigMap(
        metadata=ObjectMeta(name=obj_name, namespace='default'),
        data={'key1': 'value1', 'key2': 'value2'}
    )

    # create
    config = client.create(config)
    try:
        assert config.metadata.name == obj_name
        assert config.data['key1'] == 'value1'
        assert config.data['key2'] == 'value2'

        # replace
        config.data['key1'] = 'new value'
        config = client.replace(config)
        assert config.data['key1'] == 'new value'
        assert config.data['key2'] == 'value2'

        # patch with PatchType.STRATEGIC
        patch = {'metadata': {'labels': {'app': 'xyz'}}}
        config = client.patch(ConfigMap, name=obj_name, obj=patch)
        assert config.metadata.labels['app'] == 'xyz'

        # get
        config2 = client.get(ConfigMap, name=obj_name)
        assert config.metadata.creationTimestamp == config2.metadata.creationTimestamp

        # list
        configs = [config.metadata.name for config in client.list(ConfigMap)]
        assert obj_name in configs

    finally:
        client.delete(ConfigMap, name=obj_name)


def test_patching(obj_name):
    client = Client()
    service = Service(
        metadata=ObjectMeta(name=obj_name),
        spec=ServiceSpec(
            ports=[ServicePort(name='a', port=80, targetPort=8080)],
            selector={'app': 'not-existing'}
        )
    )

    # create
    client.create(service)
    try:
        # patch with PatchType.STRATEGIC
        patch = {'spec': {'ports': [{'name': 'b', 'port':81, 'targetPort': 8081}]}}
        service = client.patch(Service, name=obj_name, obj=patch)
        assert len(service.spec.ports) == 2
        assert {port.name for port in service.spec.ports} == {'a', 'b'}

        # strategic - patch merge key: port
        # we also try to send a Resource type for patching
        patch = Service(spec=ServiceSpec(ports=[ServicePort(name='b', port=81, targetPort=8082)]))
        service = client.patch(Service, name=obj_name, obj=patch)
        assert len(service.spec.ports) == 2

        for port in service.spec.ports:
            if port.port == 81:
                assert port.targetPort == 8082

        # patch with PatchType.MERGE
        # merge will replace the full list
        patch = {'spec': {'ports': [{'name': 'b', 'port': 81, 'targetPort': 8081}]}}
        service = client.patch(Service, name=obj_name, obj=patch, patch_type=PatchType.MERGE)
        assert len(service.spec.ports) == 1
        assert service.spec.ports[0].port == 81

        # patch with PatchType.JSON
        patch = [
            {'op': 'add', 'path': '/spec/ports/-', 'value': {'name': 'a', 'port': 80, 'targetPort': 8080}}
        ]
        service = client.patch(Service, name=obj_name, obj=patch, patch_type=PatchType.JSON)
        assert len(service.spec.ports) == 2
        assert service.spec.ports[1].port == 80

    finally:
        client.delete(Service, name=obj_name)


def test_apply(obj_name):
    client = Client(field_manager='lightkube')
    config = ConfigMap(
        apiVersion='v1',  # apiVersion and kind are required for server-side apply
        kind='ConfigMap',
        metadata=ObjectMeta(name=obj_name, namespace='default'),
        data={'key1': 'value1', 'key2': 'value2'}
    )

    # create with apply
    c = client.apply(config)
    try:
        assert c.metadata.name == obj_name
        assert c.data['key1'] == 'value1'
        assert c.data['key2'] == 'value2'

        # modify
        config.data['key2'] = 'new value'
        del config.data['key1']
        config.data['key3'] = 'value3'
        c = client.apply(config)
        assert c.data['key2'] == 'new value'
        assert c.data['key3'] == 'value3'
        assert 'key1' not in c.data

        # remove all keys
        config.data.clear()
        c = client.apply(config)
        assert not c.data

        # use the patch equivalent
        config.data['key1'] = 'new value'
        c = client.patch(ConfigMap, obj_name, config.to_dict(), patch_type=PatchType.APPLY)
        assert c.data['key1'] == 'new value'

    finally:
        client.delete(ConfigMap, name=obj_name)


def test_deletecollection(obj_name):
    client = Client()

    config = ConfigMap(
        metadata=ObjectMeta(name=obj_name, namespace=obj_name),
        data={'key1': 'value1', 'key2': 'value2'}
    )

    client.create(Namespace(metadata=ObjectMeta(name=obj_name)))

    try:
        # create
        client.create(config)
        config.metadata.name = f"{obj_name}-2"
        client.create(config)

        # k3s automatically create/recreate one extra configmap.
        maps = names(client.list(ConfigMap, namespace=obj_name))
        assert obj_name in maps
        assert f"{obj_name}-2" in maps

        client.deletecollection(ConfigMap, namespace=obj_name)
        maps = names(client.list(ConfigMap, namespace=obj_name))
        assert obj_name not in maps
        assert f"{obj_name}-2" not in maps

    finally:
        client.delete(Namespace, name=obj_name)


def test_list_all_ns(obj_name):
    client = Client()
    ns1 = obj_name
    ns2 = f"{obj_name}-2"

    config = ConfigMap(
        metadata=ObjectMeta(name=obj_name),
        data={'key1': 'value1', 'key2': 'value2'}
    )

    client.create(Namespace(metadata=ObjectMeta(name=ns1)))
    client.create(Namespace(metadata=ObjectMeta(name=ns2)))

    try:
        client.create(config, namespace=ns1)
        client.create(config, namespace=ns2)

        maps = [f"{cm.metadata.namespace}/{cm.metadata.name}" for cm in client.list(ConfigMap, namespace='*')]
        assert f"{ns1}/{obj_name}" in maps
        assert f"{ns2}/{obj_name}" in maps

    finally:
        client.delete(Namespace, name=ns1)
        client.delete(Namespace, name=ns2)


def test_crd():
    client = Client()
    fname = Path(__file__).parent.joinpath('test-crd.yaml')
    with fname.open() as f:
        crd = list(load_all_yaml(f))[0]

    CronTab = create_namespaced_resource(
        group="stable.example.com",
        version="v1",
        kind="CronTab",
        plural="crontabs",
        verbs=None
    )

    client.create(crd)
    # CRD endpoints are not ready immediately, we need to wait for condition `Established`
    client.wait(crd.__class__, name=crd.metadata.name, for_conditions=['Established'])
    try:
        client.create(CronTab(
            metadata={'name': 'my-cron'},
            spec={'cronSpec': '* * * * */5', 'image': 'my-awesome-cron-image'},
        ))

        ct = client.get(CronTab, name='my-cron')
        assert ct.metadata.name == 'my-cron'
        assert ct.spec['cronSpec'] == '* * * * */5'
    finally:
        client.delete(crd.__class__, name=crd.metadata.name)


@pytest.mark.parametrize("resource", [Node])
def test_wait_global(resource):
    client = Client()

    for obj in client.list(resource):
        client.wait(resource, obj.metadata.name, for_conditions=["Ready"])


@pytest.mark.asyncio
@pytest.mark.parametrize("resource", [Node])
async def test_wait_global_async(resource):
    client = AsyncClient()

    async for obj in client.list(resource):
        await client.wait(resource, obj.metadata.name, for_conditions=["Ready"])

    await client.close()


WAIT_NAMESPACED_PARAMS = [
    (Pod, "Ready", {"containers": [{"name": "nginx", "image": "nginx:1.21.4"}]}),
    (
        Deployment,
        "Available",
        {
            "selector": {"matchLabels": {"foo": "bar"}},
            "template": {
                "metadata": {"labels": {"foo": "bar"}},
                "spec": {"containers": [{"name": "nginx", "image": "nginx:1.21.4"}]},
            },
        },
    ),
]


@pytest.mark.parametrize("resource,for_condition,spec", WAIT_NAMESPACED_PARAMS)
def test_wait_namespaced(resource, for_condition, spec):
    client = Client()

    requested = resource.from_dict(
        {"metadata": {"generateName": "e2e-test-"}, "spec": spec}
    )
    created = client.create(requested)
    client.wait(
        resource,
        created.metadata.name,
        for_conditions=[for_condition],
    )
    client.delete(resource, created.metadata.name)


@pytest.mark.asyncio
@pytest.mark.parametrize("resource,for_condition,spec", WAIT_NAMESPACED_PARAMS)
async def test_wait_namespaced_async(resource, for_condition, spec):
    client = AsyncClient()

    requested = resource.from_dict(
        {"metadata": {"generateName": "e2e-test-"}, "spec": spec}
    )
    created = await client.create(requested)
    await client.wait(
        resource,
        created.metadata.name,
        for_conditions=[for_condition],
    )
    await client.delete(resource, created.metadata.name)

    await client.close()


@pytest.fixture(scope="function")
def sample_crd():
    client = Client()
    fname = Path(__file__).parent.joinpath('test-crd.yaml')
    with fname.open() as f:
        crd = list(load_all_yaml(f))[0]

    # modify the crd to be unique, avoiding collision with other tests
    prefix = "".join(choices(ascii_lowercase, k=5))
    crd.spec.group = f"{prefix}{crd.spec.group}"
    crd.spec.names.plural = f"{prefix}{crd.spec.names.plural}"
    crd.spec.names.singular = f"{prefix}{crd.spec.names.singular}"
    crd.spec.names.kind = f"{prefix}{crd.spec.names.kind}"
    crd.spec.names.shortnames = [f"{prefix}{shortname}" for shortname in crd.spec.names.shortNames]
    crd.metadata.name = f"{crd.spec.names.plural}.{crd.spec.group}"

    client.create(crd)
    # CRD endpoints are not ready immediately, we need to wait for condition `Established`
    client.wait(crd.__class__, name=crd.metadata.name, for_conditions=['Established'])

    yield crd

    client.delete(crd.__class__, name=crd.metadata.name)


def test_load_in_cluster_generic_resources(sample_crd):
    client = Client()

    # Assert that we do not yet have a generic resource for this CR
    cr_version = f"{sample_crd.spec.group}/{sample_crd.spec.versions[0].name}"
    cr_kind = sample_crd.spec.names.kind
    gr = get_generic_resource(cr_version, cr_kind)
    assert gr is None

    load_in_cluster_generic_resources(client)

    # Assert that we now have a generic resource for this CR
    gr = get_generic_resource(cr_version, cr_kind)
    assert gr is not None


@pytest.mark.asyncio
async def test_load_in_cluster_generic_resources_async(sample_crd):
    client = AsyncClient()

    # Assert that we do not yet have a generic resource for this CR
    cr_version = f"{sample_crd.spec.group}/{sample_crd.spec.versions[0].name}"
    cr_kind = sample_crd.spec.names.kind
    gr = get_generic_resource(cr_version, cr_kind)
    assert gr is None

    await async_load_in_cluster_generic_resources(client)

    # Assert that we now have a generic resource for this CR
    gr = get_generic_resource(cr_version, cr_kind)
    assert gr is not None
