"""
This file is part of Ludolph: hello world plugin
Copyright (C) 2015 Erigones, s. r. o.

See the LICENSE file for copying permission.
"""
# noinspection PyPep8Naming
from hello_world.__init__ import __version__ as VERSION
from ludolph.command import command, parameter_required, admin_required
from ludolph.plugins.plugin import LudolphPlugin


class Base(LudolphPlugin):
    """
    Ludolph: Hello world plugin commands.

    Sample plugin with 3 commands. Each showing how you can use Ludolph decorators
    for your plugins.
    """
    # noinspection PyUnusedLocal
    @command
    def hello_world(self, msg):
        """
        Hello world plugin greeting.

        Usage: hello-world
        """
        return 'Hi, I am hello world plugin reply!'

    # noinspection PyUnusedLocal
    @parameter_required(1)
    @command
    def hello_repeat(self, msg, *args):
        """
        Hello world plugin parameters repeater.
        Repeats all parameters passed to command, first parameter is required.

        Usage: hello-repeat <param1> <param2> <param3> <paramN>
        """
        return 'I have received this parameters: %s' % ', '.join(args)

    # noinspection PyUnusedLocal
    @admin_required
    @command
    def hello_version(self, msg):
        """
        Hello world plugin version (admin only).

        Usage: hello-version
        """
        return VERSION
