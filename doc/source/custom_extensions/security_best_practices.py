"""
Sphinx Extension to enable and list security best practices

Derived from the original documetation:
https://www.sphinx-doc.org/en/master/development/tutorials/todo.html
"""

from docutils import nodes
from docutils.parsers.rst import Directive, directives

from sphinx.application import Sphinx
from sphinx.locale import _
from sphinx.util.docutils import SphinxDirective


class SecurityBestPractice(nodes.Admonition, nodes.Element):
    """Admonition for Security Best Practices"""

    def __init__(self, *args, **kwargs):
        super(SecurityBestPractice, self).__init__(*args, **kwargs)
        self.attributes.update({"classes": ["security-best-practice"]})


class SecurityBestPracticesLists(nodes.General, nodes.Element):
    """PlaceHolder for a List of Security Best Practices"""

    pass


def visit_best_practice_node(self, node):
    self.visit_admonition(node)


def depart_best_practice_node_node(self, node):
    self.depart_admonition(node)


class BestPracticeListDirective(Directive):
    """Initializer for Security Best Practices List"""

    def run(self):
        return [SecurityBestPracticesLists("")]


class BestPracticeDirective(SphinxDirective):
    """
    Initializer for Security Best Practice. Content of run method is triggered for every security
    best practice admonition"""

    has_content = True
    option_spec = {
        "title": directives.unchanged_required,
    }

    def run(self):
        targetid = "sbp-%d" % self.env.new_serialno("sbp")  # sbp = security best practice
        targetnode = nodes.target("", "", ids=[targetid])
        title = "No title provided"
        if "title" in self.options:
            title = self.options["title"]
        node = SecurityBestPractice("\n".join(self.content))
        admonition_title = f"Security Best Practice - {title}"
        node += nodes.title(_(admonition_title), _(admonition_title))
        self.state.nested_parse(self.content, self.content_offset, node)
        if not hasattr(self.env, "all_security_best_practices"):
            self.env.all_security_best_practices = []
        self.env.all_security_best_practices.append(
            {
                "docname": self.env.docname,
                "lineno": self.lineno,
                "best_practice": node.deepcopy(),
                "target": targetnode,
                "title": title,
            }
        )
        return [targetnode, node]


def purge_best_practice(app, env, docname):
    if not hasattr(env, "all_security_best_practices"):
        return
    env.all_security_best_practices = [
        node for node in env.all_security_best_practices if node["docname"] != docname
    ]


def merge_best_practice(app, env, docnames, other):
    if not hasattr(env, "all_security_best_practices"):
        env.all_security_best_practices = []
    if hasattr(other, "all_security_best_practices"):
        env.all_security_best_practices.extend(other.all_security_best_practices)


def process_nodes(app, doctree, fromdocname):
    """
    Builds a list of all security best practices with back references to the original
    admonition.
    """
    env = app.builder.env
    if not hasattr(env, "all_security_best_practices"):
        env.all_security_best_practices = []
    for node in doctree.findall(SecurityBestPracticesLists):
        content = []
        for node_info in env.all_security_best_practices:
            title = nodes.topic()
            title += nodes.Text(node_info["title"])
            back_reference = create_back_reference(app, fromdocname, node_info)
            content.extend((title, node_info["best_practice"], back_reference))
        node.replace_self(content)


def create_back_reference(app, fromdocname, node_info):
    """Creates a sphinx paragraph node containing a reference to the original admonition."""
    back_reference = nodes.paragraph()
    newnode = nodes.reference("", "")
    reference_text = "Reference to original description"
    innernode = nodes.emphasis(_(reference_text), _(reference_text))
    newnode["refdocname"] = node_info["docname"]
    newnode["refuri"] = app.builder.get_relative_uri(fromdocname, node_info["docname"])
    newnode["refuri"] += "#" + node_info["target"]["refid"]
    newnode.append(innernode)
    back_reference += newnode
    return back_reference


def setup(app: Sphinx):
    """Initializer for the Security Best Practices Extension"""
    app.add_node(SecurityBestPracticesLists)
    app.add_node(
        SecurityBestPractice,
        html=(visit_best_practice_node, depart_best_practice_node_node),
        latex=(visit_best_practice_node, depart_best_practice_node_node),
        text=(visit_best_practice_node, depart_best_practice_node_node),
    )
    app.add_directive("security-best-practice", BestPracticeDirective)
    app.add_directive("security-best-practices-list", BestPracticeListDirective)
    app.connect("doctree-resolved", process_nodes)
    app.connect("env-purge-doc", purge_best_practice)
    app.connect("env-merge-info", merge_best_practice)

    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
