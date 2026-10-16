VERSION = {"value": (12, 4, 6)}


class _App(object):
    browser = None  # set by the test harness to the fake song's Browser

    def get_major_version(self):
        return VERSION["value"][0]

    def get_minor_version(self):
        return VERSION["value"][1]

    def get_bugfix_version(self):
        return VERSION["value"][2]


APP = _App()


def get_application():
    return APP
