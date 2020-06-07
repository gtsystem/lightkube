from jinja2 import Template

def get_template(fname):
    with open(fname) as f:
        return Template(f.read())

template.render(name='John')


def make_class(f, name, properties, actions, classes):
    classes = ", ".join(cl for cl in classes)
    f.write("@dataclass\n")
    f.write(f"class {name}({classes}):\n")
    f.write(f"    class ApiInfo:\n")
    for k, v in properties.items():
        f.write(f"        {k} = {v}\n")
    for k, v in actions.items():
        f.write(f"    {k}: ClassVar = {v}\n")
    f.write(f"\n\n")
