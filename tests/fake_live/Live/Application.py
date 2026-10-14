VERSION = {"value": (12, 4, 6)}


class _App(object):
    def get_major_version(self):
        return VERSION["value"][0]

    def get_minor_version(self):
        return VERSION["value"][1]

    def get_bugfix_version(self):
        return VERSION["value"][2]


def get_application():
    return _App()
