ludolph-zabbix
##############

`Ludolph <https://github.com/erigones/Ludolph>`_: Zabbix API plugin

.. image:: https://badge.fury.io/py/ludolph-zabbix.png
    :target: http://badge.fury.io/py/ludolph-zabbix


Installation
------------

- Install the latest released version using pip::

    pip install ludolph-zabbix

- Add new plugin section into Ludolph configuration file::

    [ludolph_zabbix.zapi]
    # Zabbix server URI
    server = https://zabbix.example.com/zabbix
    # ssl_verify = true

    # Zabbix credentials
    username = ludolph
    password =

    # HTTP authetication
    #httpuser =
    #httppasswd =

- Reload Ludolph::

    service ludolph reload


**Dependencies:**

- `Ludolph <https://github.com/erigones/Ludolph>`_ (0.9.0+)
- `zabbix-api-erigones <https://github.com/erigones/zabbix-api/>`_ (1.2.2+)


Links
-----

- Wiki: https://github.com/erigones/Ludolph/wiki/How-to-configure-Zabbix-to-work-with-Ludolph
- Bug Tracker: https://github.com/erigones/ludolph-zabbix/issues
- Google+ Community: https://plus.google.com/u/0/communities/112192048027134229675
- Twitter: https://twitter.com/erigones


License
-------

For more information see the `LICENSE <https://github.com/erigones/ludolph-zabbix/blob/master/LICENSE>`_ file.

####

The Ludolph Zabbix plugin is inspired by `Dante <http://www.digmia.com>`_.
