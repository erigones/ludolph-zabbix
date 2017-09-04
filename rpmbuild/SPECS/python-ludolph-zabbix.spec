# Created by pyp2rpm-3.2.1
%global pypi_name ludolph-zabbix

Name:           python-%{pypi_name}
Version:        1.7
Release:        1%{?dist}
Summary:        Ludolph: Zabbix API plugin

License:        MIT
URL:            https://github.com/erigones/ludolph-zabbix/
Source0:        https://files.pythonhosted.org/packages/source/l/%{pypi_name}/%{pypi_name}-%{version}.tar.gz
BuildArch:      noarch
 
BuildRequires:  python2-devel
BuildRequires:  python2-setuptools
 
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools

%global desc Ludolph: Zabbix API plugin.\
\
Plugin for Ludolph Monitoring Jabber Bot support Zabbix monitoring system.

%description
%{desc}

%package -n     python2-%{pypi_name}
Summary:        %{summary}
%{?python_provide:%python_provide python2-%{pypi_name}}
 
Requires:       python2-ludolph
Requires:       python2-zabbix-api-erigones
%description -n python2-%{pypi_name}
%{desc}
Python 2 module with Ludolph: Zabbix API plugin. Use the python3-ludolph and\
python3-%{pypi_name} package to get the actual application and service.


%package -n     python3-%{pypi_name}
Summary:        %{summary}
%{?python_provide:%python_provide python3-%{pypi_name}}
 
Requires:       python3-ludolph
Requires:       python3-zabbix-api-erigones
%description -n python3-%{pypi_name}
%{desc}

%prep
%autosetup -n %{pypi_name}-%{version}
# Remove bundled egg-info
rm -rf %{pypi_name}.egg-info

%build
%py2_build
%py3_build

%install
%py3_install
%py2_install


%files -n python2-%{pypi_name}
%license LICENSE
%doc README.rst
%{python2_sitelib}/ludolph_zabbix
%{python2_sitelib}/ludolph_zabbix-%{version}-py?.?.egg-info

%files -n python3-%{pypi_name}
%license LICENSE
%doc README.rst
%{python3_sitelib}/ludolph_zabbix
%{python3_sitelib}/ludolph_zabbix-%{version}-py?.?.egg-info

%changelog
* Mon Sep 04 2017 ricco <richard.kellner@gmail.com> - 1.7-1
- Initial package.
