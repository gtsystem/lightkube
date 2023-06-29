import textwrap
from pathlib import Path
from unittest import mock

import pytest
import yaml

from lightkube import codecs
from lightkube.resources.core_v1 import ConfigMap
from lightkube.resources.rbac_authorization_v1 import Role
from lightkube.models.meta_v1 import ObjectMeta
from lightkube import generic_resource as gr
from lightkube import LoadResourceError

data_dir = Path(__file__).parent.joinpath('data')


@pytest.fixture()
def mocked_created_resources():
    """Isolates the module variable generic_resource._created_resources to avoid test spillover"""
    created_resources_dict = {}
    with mock.patch("lightkube.generic_resource._created_resources", created_resources_dict) as mocked_created_resources:
        yield mocked_created_resources


def test_from_dict():
    config_map = codecs.from_dict({
        'apiVersion': 'v1',
        'kind': 'ConfigMap',
        'metadata': {'name': 'config-name', 'labels': {'label1': 'value1'}},
        'data': {
            'file1.txt': 'some content here',
            'file2.txt': 'some other content'
        }
    })
    assert isinstance(config_map, ConfigMap)
    assert config_map.kind == 'ConfigMap'
    assert config_map.apiVersion == 'v1'
    assert config_map.metadata.name == 'config-name'
    assert config_map.metadata.labels['label1'] == 'value1'
    assert config_map.data['file1.txt'] == 'some content here'
    assert config_map.data['file2.txt'] == 'some other content'

    role = codecs.from_dict({
        'apiVersion': 'rbac.authorization.k8s.io/v1',
        'kind': 'Role',
        'metadata': {'name': 'read-pod'},
        'rules': [{
            'apiGroup': '',
            'resources': ['pods'],
            'verbs': ['get','watch', 'list']
        }]
    })
    assert isinstance(role, Role)
    assert role.kind == 'Role'
    assert role.apiVersion == 'rbac.authorization.k8s.io/v1'
    assert role.metadata.name == 'read-pod'
    assert role.rules[0].resources == ['pods']


def test_from_dict_wrong_model():
    # provided argument must actually be a dict
    with pytest.raises(LoadResourceError, match='.*not a dict'):
        codecs.from_dict([])

    # apiVersion and kind are required
    with pytest.raises(LoadResourceError, match=".*key 'apiVersion' missing"):
        codecs.from_dict({
            'kind': 'ConfigMap',
            'metadata': {'name': 'config-name'},
        })


def test_from_dict_generic_res():
    Mydb = gr.create_namespaced_resource('myapp.com', 'v1', 'Mydb', 'mydbs')
    db = codecs.from_dict({
        'apiVersion': 'myapp.com/v1',
        'kind': 'Mydb',
        'metadata': {'name': 'db1'},
        'key': {'a': 'b', 'c': 'd'}
    })
    assert isinstance(db, Mydb)
    assert db.kind == 'Mydb'
    assert db.apiVersion == 'myapp.com/v1'
    assert db.metadata.name == 'db1'
    assert 'key' in db
    assert db['key'] == {'a': 'b', 'c': 'd'}

    # Try with a generic resource with .k8s.io version
    # https://github.com/gtsystem/lightkube/issues/18
    version = "testing.k8s.io/v1"
    kind = "Testing"
    group, version_n = version.split("/")
    Testing = gr.create_namespaced_resource(group=group, version=version_n, kind=kind,
                                         plural=f"{kind.lower()}s")
    testing = codecs.from_dict({
        'apiVersion': version,
        'kind': kind,
        'metadata': {'name': 'testing1'},
        'key': {'a': 'b', 'c': 'd'}
    })
    assert isinstance(testing, Testing)
    assert testing.kind == kind
    assert testing.apiVersion == version
    assert testing.metadata.name == 'testing1'
    assert 'key' in testing
    assert testing['key'] == {'a': 'b', 'c': 'd'}


def test_from_dict_not_found():
    with pytest.raises(LoadResourceError):
        codecs.from_dict({'apiVersion': 'myapp2.com/v1', 'kind': 'Mydb'})

    with pytest.raises(AttributeError):
        codecs.from_dict({'apiVersion': 'v1', 'kind': 'Missing'})

    with pytest.raises(LoadResourceError):
        codecs.from_dict({'apiVersion': 'extra/v1', 'kind': 'Missing'})

    # Try with an undefined generic resource with .k8s.io version
    # https://github.com/gtsystem/lightkube/issues/18
    with pytest.raises(LoadResourceError):
        codecs.from_dict({'apiVersion': "undefined.k8s.io/v1", 'kind': 'Missing'})

@pytest.mark.parametrize(
    "yaml_file",
    (
            "example-def.yaml",
            "example-def-with-nulls.yaml",
            "example-def-with-lists.yaml"
    )
)
def test_load_all_yaml_static(yaml_file):
    objs = list(codecs.load_all_yaml(data_dir.joinpath(yaml_file).read_text()))
    kinds = [o.kind for o in objs]

    assert kinds == ['Secret', 'Mydb', 'Service', 'Deployment']

    with data_dir.joinpath('example-def.yaml').open() as f:
        objs = list(codecs.load_all_yaml(f))
    kinds = [o.kind for o in objs]

    assert kinds == ['Secret', 'Mydb', 'Service', 'Deployment']


def test_load_all_yaml_template():
    objs = list(codecs.load_all_yaml(
        data_dir.joinpath('example-def.tmpl').read_text(),
        context={'test': 'xyz'})
    )
    kinds = [o.kind for o in objs]

    assert kinds == ['Secret', 'Mydb', 'Service', 'Deployment']
    assert objs[1].metadata.name == 'bla-xyz'

    with data_dir.joinpath('example-def.tmpl').open() as f:
        objs = list(codecs.load_all_yaml(f, context={'test': 'xyz'}))
    kinds = [o.kind for o in objs]

    assert kinds == ['Secret', 'Mydb', 'Service', 'Deployment']
    assert objs[1].metadata.name == 'bla-xyz'


def test_load_all_yaml_template_env():
    import jinja2
    env = jinja2.Environment()
    env.globals['test'] = 'global'

    objs = list(codecs.load_all_yaml(
        data_dir.joinpath('example-def.tmpl').read_text(),
        context={},
        template_env=env)
    )
    kinds = [o.kind for o in objs]

    assert kinds == ['Secret', 'Mydb', 'Service', 'Deployment']
    assert objs[1].metadata.name == 'bla-global'

    with data_dir.joinpath('example-def.tmpl').open() as f:
        objs = list(codecs.load_all_yaml(f, context={}, template_env=env))
    kinds = [o.kind for o in objs]

    assert kinds == ['Secret', 'Mydb', 'Service', 'Deployment']
    assert objs[1].metadata.name == 'bla-global'

    # template_env is not an environment
    with pytest.raises(LoadResourceError, match='.*valid jinja2 template'):
        codecs.load_all_yaml(
            data_dir.joinpath('example-def.tmpl').read_text(),
            context={},
            template_env={}
        )


def test_load_all_yaml_all_null():
    yaml_file = "example-def-null.yaml"
    objs = list(codecs.load_all_yaml(data_dir.joinpath(yaml_file).read_text()))
    assert len(objs) == 0


@mock.patch('lightkube.codecs.jinja2', new=None)
def test_load_all_yaml_missing_dependency():
    with pytest.raises(ImportError, match='.*requires jinja2.*'):
        codecs.load_all_yaml(
            data_dir.joinpath('example-def.tmpl').read_text(),
            context={'test': 'xyz'}
        )


@pytest.mark.parametrize(
    "create_resources_for_crds",
    [
        True,   # generic resources should be created
        False,  # no generic resources should be created
    ]
)
def test_load_all_yaml_creating_generic_resources(create_resources_for_crds, mocked_created_resources):
    template_yaml = data_dir.joinpath('example-multi-version-crd.yaml').read_text()
    template_dict = list(yaml.safe_load_all(template_yaml))[0]

    expected_group = template_dict["spec"]["group"]
    expected_kind = template_dict["spec"]["names"]["kind"]

    # Confirm no generic resources exist before testing
    assert len(gr._created_resources) == 0

    objs = list(codecs.load_all_yaml(
        template_yaml,
        create_resources_for_crds=create_resources_for_crds,
    ))

    # Confirm expected resources exist
    if create_resources_for_crds:
        for version in template_dict["spec"]["versions"]:
            resource = gr.get_generic_resource(f"{expected_group}/{version['name']}", expected_kind)
            assert resource is not None

        # Confirm we did not make any extra resources
        assert len(gr._created_resources) == len(template_dict["spec"]["versions"])
    else:
        # Confirm we did not make any resources
        assert len(gr._created_resources) == 0

    assert len(objs) == 1


def test_dump_all_yaml():
    cm = ConfigMap(
        apiVersion='v1', kind='ConfigMap',
        metadata=ObjectMeta(name='xyz', labels={'x': 'y'})
    )
    Mydb = gr.create_namespaced_resource('myapp.com', 'v1', 'Mydb', 'mydbs')

    db = Mydb(
        apiVersion='myapp.com/v1', kind='Mydb',
        metadata=ObjectMeta(name='db1'), xyz={'a': 'b'}
    )

    res = codecs.dump_all_yaml([cm, db])
    expected = textwrap.dedent("""
        apiVersion: v1
        kind: ConfigMap
        metadata:
          labels:
            x: y
          name: xyz
        ---
        apiVersion: myapp.com/v1
        kind: Mydb
        metadata:
          name: db1
        xyz:
          a: b
    """).lstrip()
    assert res == expected

    res = codecs.dump_all_yaml([db, cm], indent=4)
    expected = textwrap.dedent("""
        apiVersion: myapp.com/v1
        kind: Mydb
        metadata:
            name: db1
        xyz:
            a: b
        ---
        apiVersion: v1
        kind: ConfigMap
        metadata:
            labels:
                x: y
            name: xyz
    """).lstrip()
    assert res == expected

