from string import Template


class DottedTemplate(Template):
    braceidpattern = r"(?a:(?:\\.|[^.$\\{}])+(?:\.(?:\\.|[^.$\\{}])+)*)"
