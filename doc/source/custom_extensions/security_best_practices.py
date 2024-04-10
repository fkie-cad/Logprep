"""
Security Best Practices
=======================

Sphinx Extension to enable and list security best practices

Derived from the original documentation:
https://www.sphinx-doc.org/en/master/development/tutorials/todo.html

Usage
-----

The extension enables two different rst directives, the first acts like a single note/admonition
and lets you describe a current best practice somewhere in the documentation.
An example would look like:

.. code-block:: rst

    .. security-best-practice::
       :title: Example Best Practice
       :location: configuration.example.param
       :suggested-value: True

       The example.param should always be set to true

The options `location` and `suggested-value` are optional and are only used to fill the excel
check list, they are not rendered in the actual sphinx documentation.

The second directive collects all these admonitions and creates a list of them.
This can simply be added by using the following snippet to a file:

.. code-block:: rst

    .. security-best-practices-list::

Lastly the extension generates an excel sheet with the best practices as checklist.
In order to expose it into the documentation you have to use the following resource link:

.. code-block:: rst

    :download:`Best Practice Check List <../_static/security-best-practices-check-list.xlsx>`

Note that the filepath and name must match this exact example and that the sphinx config needs to
create this file in the docs source directory.

Known limitations
-----------------

At the moment it is not possible to add `:ref:` links to security best practice admonitions,
when the `security-best-practices-list` directive is used.
When creating the list it is not possible yet to resolve the links, leading to an unknown pending
xref exception.
"""

import pandas as pd
from docutils import nodes
from docutils.parsers.rst import Directive, directives
from openpyxl.styles import Alignment
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


def depart_best_practice_node(self, node):
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
        "location": directives.unchanged,
        "suggested-value": directives.unchanged,
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
                "meta": {
                    "title": title,
                    "location": self.options.get("location", ""),
                    "suggested-value": self.options.get("suggested-value", ""),
                },
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
            title += nodes.Text(node_info.get("meta").get("title"))
            back_reference = create_back_reference(app, fromdocname, node_info)
            content.extend((title, node_info["best_practice"], back_reference))
        node.replace_self(content)
    create_xls_checklist(app, env)


def create_xls_checklist(app, env):
    description = []
    for node in env.all_security_best_practices:
        meta_info = node.get("meta")
        text = node.get("best_practice").rawsource
        description.append(
            {
                "Topic": meta_info.get("title"),
                "Requirement": text,
                "Configuration Location": meta_info.get("location"),
                "Suggested Value": meta_info.get("suggested-value"),
                "Is": "",
                "Comment": "",
            }
        )
    dataframe = pd.DataFrame(description)
    download_file_name = "security-best-practices-check-list"
    download_file_obj = [env.dlfiles[key] for key in env.dlfiles if download_file_name in key][0]
    download_file_path = download_file_obj[1]
    full_file_path = f"{app.outdir}/_downloads/{download_file_path}"
    writer = pd.ExcelWriter(full_file_path, engine="openpyxl")
    dataframe.to_excel(writer, index=False, sheet_name="Security Best Practices")
    worksheet = writer.sheets["Security Best Practices"]
    column_width = {"A": 60, "B": 60, "C": 30, "D": 30, "E": 30, "F": 30, "G": 30}
    for column, width in column_width.items():
        worksheet.column_dimensions[column].width = width
    worksheet["B2"].alignment = Alignment(wrap_text=True)
    writer.close()


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
    app.add_node(
        SecurityBestPractice,
        html=(visit_best_practice_node, depart_best_practice_node),
        latex=(visit_best_practice_node, depart_best_practice_node),
        text=(visit_best_practice_node, depart_best_practice_node),
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
