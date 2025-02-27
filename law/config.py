# coding: utf-8

"""
law config parser implementation.
"""

__all__ = [  # noqa
    "Config", "sections", "options", "keys", "items", "update", "include", "get", "getint",
    "getfloat", "getboolean", "get_default", "get_expanded", "get_expanded_int",
    "get_expanded_float", "get_expanded_boolean", "is_missing_or_none", "find_option", "set",
    "has_section", "has_option", "remove_option",
]


import os
import re
import tempfile

import luigi
import six
from six.moves.configparser import ConfigParser

from law.util import no_value, brace_expand, str_to_int


def law_home_path(*paths):
    home = os.getenv("LAW_HOME") or os.path.expandvars(os.path.expanduser("$HOME/.law"))
    return os.path.normpath(os.path.join(home, *(str(path) for path in paths)))


class Config(ConfigParser):
    """
    Custom law configuration parser with a few additions on top of the standard python
    ``ConfigParser``. Most notably, this class adds config *inheritance* via :py:meth:`update` and
    :py:meth:`include`, a mechanism to synchronize with the luigi configuration parser, option
    referencing, and environment variable expansion.

    When *config_file* is set, it is loaded during setup. When empty, and *skip_fallbacks* is
    *False*, the default config file locations defined in :py:attr:`_config_files` are checked. By
    default, the default configuration :py:attr:`_default_config` is loaded, which can be prevented
    by setting *skip_defaults* to *True*.

    .. py:classattribute:: _instance
       type: Config

       Global instance of this class.

    .. py:classattribute:: _default_config
       type: dict

       Default configuration.

    .. py:classattribute:: _config_files
       type: list

       List of configuration files that are checked during setup (unless *skip_fallbacks* is
       *True*). When a file exists, the check is stopped. Therefore, the order is important here.
    """

    _instance = None

    _default_config = {
        "core": {
            "law_home": law_home_path(),
            "index_file": os.getenv("LAW_INDEX_FILE") or law_home_path("index"),
            "software_dir": os.getenv("LAW_SOFTWARE_DIR") or law_home_path("software"),
            "inherit": None,
            "extend": None,
            "sync_env": True,
            "sync_luigi_config": True,
        },
        "logging": {
            "law": os.getenv("LAW_LOG_LEVEL") or "WARNING",
            "gfal2": "WARNING",
        },
        "modules": {},
        "task": {
            "colored_repr": False,
            "colored_str": True,
            "interactive_format": "fancy",
            "interactive_line_breaks": True,
        },
        "target": {
            "colored_repr": False,
            "colored_str": True,
            "expand_path_repr": False,
            "filesize_repr": False,
            "tmp_dir": os.getenv("LAW_TARGET_TMP_DIR") or tempfile.gettempdir(),
            "tmp_dir_perm": 0o0770,
            "default_local_fs": "local_fs",
            # contrib
            "default_wlcg_fs": "wlcg_fs",
            "default_dropbox_fs": "dropbox_fs",
        },
        "local_fs": {
            "base": "/",
            # defined by FileSystem
            "has_permissions": True,
            "default_file_perm": None,
            "default_dir_perm": None,
            "create_file_dir": True,
        },
        "wlcg_fs": {
            # defined by FileSystem
            "has_permissions": False,
            "default_file_perm": None,
            "default_dir_perm": None,
            "create_file_dir": False,  # requires gfal_transfer_create_parent to be True
            # defined by RemoteFileInterface
            "base": None,
            "base_stat": None,
            "base_exists": None,
            "base_chmod": None,
            "base_unlink": None,
            "base_rmdir": None,
            "base_mkdir": None,
            "base_listdir": None,
            "base_filecopy": None,
            "retries": 1,
            "retry_delay": "5s",
            "random_base": True,
            # defined by RemoteFileSystem
            "validate_copy": False,
            "use_cache": False,
            # define by RemoteCache
            "cache_root": None,
            "cache_cleanup": None,
            "cache_max_size": "0MB",
            "cache_mtime_patience": 1.0,
            "cache_file_perm": 0o0660,
            "cache_dir_perm": 0o0770,
            "cache_wait_delay": "5s",
            "cache_max_waits": 120,
            "cache_global_lock": False,
            # defined by GFALFileInterface
            "gfal_atomic_contexts": False,
            "gfal_transfer_timeout": 3600,
            "gfal_transfer_checksum_check": False,
            "gfal_transfer_nbstreams": 1,
            "gfal_transfer_overwrite": True,
            "gfal_transfer_create_parent": True,
            "gfal_transfer_strict_copy": False,
            # defined by WLCGFileSystem
            # no dedicated configs
        },
        "dropbox_fs": {
            # defined by FileSystem
            "has_permissions": False,
            "default_file_perm": None,
            "default_dir_perm": None,
            "create_file_dir": False,  # requires gfal_transfer_create_parent to be True
            # defined by RemoteFileInterface
            "base": None,
            "base_stat": None,
            "base_exists": None,
            "base_chmod": None,
            "base_unlink": None,
            "base_rmdir": None,
            "base_mkdir": None,
            "base_listdir": None,
            "base_filecopy": None,
            "retries": 1,
            "retry_delay": "5s",
            "random_base": True,
            # defined by RemoteFileSystem
            "validate_copy": False,
            "use_cache": False,
            # define by RemoteCache
            "cache_root": None,
            "cache_cleanup": None,
            "cache_max_size": "0MB",
            "cache_mtime_patience": 1.0,
            "cache_file_perm": 0o0660,
            "cache_dir_perm": 0o0770,
            "cache_wait_delay": "5s",
            "cache_max_waits": 120,
            "cache_global_lock": False,
            # defined by GFALFileInterface
            "gfal_atomic_contexts": False,
            "gfal_transfer_timeout": 3600,
            "gfal_transfer_checksum_check": False,
            "gfal_transfer_nbstreams": 1,
            "gfal_transfer_overwrite": True,
            "gfal_transfer_create_parent": True,
            "gfal_transfer_strict_copy": False,
            # defined by DropboxFileSystem
            "dropbox_app_key": None,
            "dropbox_app_secret": None,
            "dropbox_access_token": None,
        },
        "job": {
            "job_file_dir": os.getenv("LAW_JOB_FILE_DIR") or tempfile.gettempdir(),
            "job_file_dir_mkdtemp": True,
            "job_file_dir_cleanup": True,
            # contrib
            "arc_job_file_dir": None,
            "arc_job_file_dir_mkdtemp": None,
            "arc_job_file_dir_cleanup": None,
            "arc_chunk_size_submit": 25,
            "arc_chunk_size_cancel": 25,
            "arc_chunk_size_cleanup": 25,
            "arc_chunk_size_query": 20,
            "glite_job_file_dir": None,
            "glite_job_file_dir_mkdtemp": None,
            "glite_job_file_dir_cleanup": None,
            "glite_chunk_size_cancel": 25,
            "glite_chunk_size_cleanup": 25,
            "glite_chunk_size_query": 25,
            "htcondor_job_file_dir": None,
            "htcondor_job_file_dir_mkdtemp": None,
            "htcondor_job_file_dir_cleanup": False,
            "htcondor_chunk_size_submit": 25,
            "htcondor_chunk_size_cancel": 25,
            "htcondor_chunk_size_query": 25,
            "lsf_job_file_dir": None,
            "lsf_job_file_dir_mkdtemp": None,
            "lsf_job_file_dir_cleanup": False,
            "lsf_chunk_size_cancel": 25,
            "lsf_chunk_size_query": 25,
            "slurm_job_file_dir": None,
            "slurm_job_file_dir_mkdtemp": None,
            "slurm_job_file_dir_cleanup": False,
            "slurm_chunk_size_cancel": 25,
            "slurm_chunk_size_query": 25,
        },
        "notifications": {
            "mail_recipient": None,
            "mail_sender": None,
            "mail_smtp_host": "127.0.0.1",
            "mail_smtp_port": 25,
            # contrib
            "slack_token": None,
            "slack_channel": None,
            "slack_mention_user": None,
            "telegram_token": None,
            "telegram_chat": None,
            "telegram_mention_user": None,
        },
        "bash_sandbox": {
            "stagein_dir_name": "stagein",
            "stageout_dir_name": "stageout",
            "login": False,
        },
        "bash_sandbox_env": {},
        "venv_sandbox": {
            "stagein_dir_name": "stagein",
            "stageout_dir_name": "stageout",
        },
        "venv_sandbox_env": {},
        "docker_sandbox": {
            "stagein_dir_name": "stagein",
            "stageout_dir_name": "stageout",
            "uid": None,
            "gid": None,
            "forward_dir": "/law_forward",
            "python_dir": "py",
            "bin_dir": "bin",
        },
        "docker_sandbox_env": {},
        "docker_sandbox_volumes": {},
        "singularity_sandbox": {
            "stagein_dir_name": "stagein",
            "stageout_dir_name": "stageout",
            "uid": None,
            "gid": None,
            "forward_dir": "/law_forward",
            "python_dir": "py",
            "bin_dir": "bin",
            "allow_binds": True,
            "forward_law": True,
        },
        "singularity_sandbox_env": {},
        "singularity_sandbox_volumes": {},
    }

    _config_files = ["$LAW_CONFIG_FILE", "law.cfg", law_home_path("config"), "etc/law/config"]

    _option_ref_regex = re.compile(r"^\&(::(?P<section>[^\:]+))?::(?P<option>.+)$")

    _env_option_regex = re.compile(r"^LAW__([a-zA-Z0-9_]+)__([a-zA-Z0-9_]+)$")

    @classmethod
    def instance(cls, *args, **kwargs):
        """
        Creates an instance of this class with all *args* and *kwargs*, saves it in
        :py:attr:`_instance`, and returns it. When :py:attr:`_instance` was already set before, no
        new instance is created.
        """
        if cls._instance is None:
            cls._instance = cls(*args, **kwargs)
        return cls._instance

    @classmethod
    def _parse_option_ref(cls, value, default_section=None):
        m = cls._option_ref_regex.match(value)
        if not m:
            return None
        return (m.group("section") or default_section, m.group("option"))

    def __init__(self, config_file="", skip_defaults=False, skip_fallbacks=False,
            skip_includes=False, skip_env_sync=False, skip_luigi_sync=False):
        ConfigParser.__init__(self, allow_no_value=True)

        # lookup to correct config file
        self.config_file = None
        config_files = []
        if config_file:
            config_files.append(config_file)
        if not skip_fallbacks:
            config_files += self._config_files
        for cf in config_files:
            cf = os.path.expandvars(os.path.expanduser(cf))
            cf = os.path.normpath(os.path.abspath(cf))
            if os.path.isfile(cf):
                self.config_file = cf
                break

        # helper to include additional configs
        def include_configs(filenames):
            if isinstance(filenames, six.string_types):
                filenames = [f.strip() for f in brace_expand(filenames.strip(), split_csv=True)]
            for filename in filenames or []:
                if not filename:
                    continue
                # try to resolve filename relative to the main config file
                if self.config_file:
                    basedir = os.path.dirname(self.config_file)
                    filename = os.path.normpath(os.path.join(basedir, filename))
                self.include(filename)

        # load defaults
        if not skip_defaults:
            self.update(self._default_config)

        # load the content of inherited configs
        if not skip_includes and self.config_file:
            # eagerly read the config file to get a glimpse of the files to inherit from
            c = self.__class__(self.config_file, skip_defaults=True, skip_fallbacks=True,
                skip_includes=True, skip_env_sync=True, skip_luigi_sync=True)
            opt = "inherit"
            if c.has_option("core", "inherit_configs") and not c.get_expanded("core", "inherit"):
                # print a warning, not using the logger yet since it's not initialized at this point
                opt = "inherit_configs"
                print(
                    "INFO: the 'core.inherit_configs' option is deprecated and will be removed in a "
                    "future release of law; please use 'core.inherit' instead",
                )
            include_configs(c.get_expanded("core", opt))

        # load the actual config file if given
        if self.config_file:
            self.read(self.config_file)

        # load the content of extended configs
        if not skip_includes:
            opt = "extend"
            if self.has_option("core", "extend_configs") and not self.get_expanded("core", "extend"):
                # print a warning, not using the logger yet since it's not initialized at this point
                opt = "extend_configs"
                print(
                    "INFO: the 'core.extend_configs' option is deprecated and will be removed in a "
                    "future release of law; please use 'core.extend' instead",
                )
            include_configs(self.get_expanded("core", opt))

        # sync with environment variables
        if not skip_env_sync and self.get_expanded_boolean("core", "sync_env"):
            self.sync_env()

        # sync with luigi configuration
        if not skip_luigi_sync and self.get_expanded_boolean("core", "sync_luigi_config"):
            self.sync_luigi_config()

    def _convert_to_boolean(self, value):
        # py2 backport
        if six.PY3:
            return super(Config, self)._convert_to_boolean(value)

        if value.lower() not in self._boolean_states:
            raise ValueError("Not a boolean: {}".format(value))
        return self._boolean_states[value.lower()]

    def _get_type_converter(self, type, value):
        if type in (str, "str", "s"):
            return str
        if type in (int, "int", "i"):
            return str_to_int
        elif type in (float, "float", "f"):
            return float
        elif type in (bool, "bool", "boolean", "b"):
            if isinstance(value, six.string_types):
                return self._convert_to_boolean
            else:
                return bool
        else:
            raise ValueError("unknown 'type' argument ({}), must be 'str', 'int', 'float', or "
                "'bool'".format(type))

    def optionxform(self, option):
        """"""
        return option

    def options(self, section, prefix=None, expand_vars=True, expand_user=True):
        """
        Returns all options of a *section* in a list. When *prefix* is set, only options starting
        with that prefix are considered. Environment variable expansion is performed on every
        returned option name, depending on whether *expand_vars* and *expand_user* are *True*.
        """
        options = []
        for option in ConfigParser.options(self, section):
            if prefix and not option.startswith(prefix):
                continue
            if expand_vars:
                option = os.path.expandvars(option)
            if expand_user:
                option = os.path.expanduser(option)
            options.append(option)
        return options

    def keys(self, *args, **kwargs):
        # deprecation warning until v0.1 (also remove the entry in __all__ above)
        logger.warning("the use of {0}.keys() is deprecated, please use {0}.options() "
            "instead".format(self.__class__.__name__))

        return self.options(*args, **kwargs)

    def items(self, section, prefix=None, expand_vars=True, expand_user=True, **kwargs):
        """
        Returns a dictionary of key-value pairs for the given *section*. When *prefix* is set, only
        options starting with that prefix are considered. Environment variable expansion is
        performed on every returned option name and corresponding value, depending on whether
        *expand_vars* and *expand_user* are *True*. Internally, py:meth:`get_expanded` is used
        to perform value expansion and type interpolation, and is passed all *kwargs*.
        """
        options = self.options(section, prefix=prefix, expand_vars=expand_vars,
            expand_user=expand_user)
        return [
            (opt, self.get_expanded(section, opt, expand_vars=expand_vars,
                expand_user=expand_user, **kwargs))
            for opt in options
        ]

    def update(self, data, overwrite=True, overwrite_sections=None, overwrite_options=None):
        """
        Updates the currently stored configuration with new *data*, given as a dictionary. When
        *overwrite_sections* is *False*, sections in *data* that are already present in the current
        config are skipped. When *overwrite_options* is *False*, existing options are not
        overwritten. When *None*, both *overwrite_sections* and *overwrite_options* default to
        *overwrite*.
        """
        if overwrite_sections is None:
            overwrite_sections = overwrite
        if overwrite_options is None:
            overwrite_options = overwrite

        for section, _data in six.iteritems(data):
            # add the section when it does not exist, and continue when it does but not overwriting
            if not self.has_section(section):
                self.add_section(section)
            elif not overwrite_sections:
                continue

            for option, value in six.iteritems(_data):
                # set the option when overwriting anyway, or when it does not exist
                if overwrite_options or not self.has_option(section, option):
                    self.set(section, option, str(value))

    def include(self, filename, *args, **kwargs):
        """
        Updates the current config by that found in *filename*. All *args* and *kwargs* are
        forwarded to :py:meth:`update`.
        """
        p = self.__class__(filename, skip_defaults=True, skip_fallbacks=True, skip_env_sync=True,
            skip_luigi_sync=True)
        self.update(p._sections, *args, **kwargs)

    def get_default(self, section, option, default=None, type=None, expand_vars=False,
            expand_user=False, split_csv=False, dereference=True, default_when_none=True,
            _skip_refs=None):
        """ get_default(section, option, default=None, type=None, expand_vars=False, expand_user=False, split_csv=False, dereference=True, default_when_none=True)
        Returns the config value defined by *section* and *option*. When either the section or the
        option does not exist, the *default* value is returned instead. When *type* is set, it must
        be either `"str"`, `"int"`, `"float"`, or `"boolean"`. When *expand_vars* is *True*,
        environment variables are expanded. When *expand_user* is *True*, user variables are
        expanded as well. Sequences of values can be identified, split by comma and returned as a
        list when *split_csv* is *True*, which will also trigger brace expansion.

        Also, options retrieved by this method are allowed to refer to values of other options
        within the config, even to those in other sections. The syntax for config references is
        ``&[::section]::option``. When no section is given, the value refers to an option in the
        same section. Example:

        .. code-block:: ini

            [my_section]
            a: 123
            b: &::a              # 123, refers to "a" in the same section

            [bar_section]
            a: &::my_section::a  # 123, refers to "a" in "my_section"

        This behavior is the default and, if desired, can be disabled by setting *dereference* to
        *False*. When the reference is not resolvable, the default value is returned.

        When *default_when_none* is *True* and the option was found but its value is *None* or
        ``"None"`` (case-insensitive), the *default* is returned.
        """  # noqa
        # return the default when either the section or the option does not exist
        if not self.has_section(section) or not self.has_option(section, option):
            return default

        # get the value
        value = self.get(section, option)

        # handle variable expansion and dereferencing when value is a string
        # (which should always be the case, but subclasses might overwrite get())
        if isinstance(value, six.string_types):
            # expand
            if expand_vars:
                value = os.path.expandvars(value)
            if expand_user:
                value = os.path.expanduser(value)

            # resolve references
            if dereference:
                ref = self._parse_option_ref(value, default_section=section)
                if ref:
                    # to avoid circular references, keep track of already resolved ones
                    if _skip_refs is None:
                        _skip_refs = []
                    elif ref in _skip_refs:
                        return default
                    _skip_refs.append(ref)

                    # return the referenced value
                    return self.get_default(*ref, default=default, type=type,
                        expand_vars=expand_vars, expand_user=expand_user, dereference=dereference,
                        default_when_none=default_when_none, _skip_refs=_skip_refs)

        # interpret None and "None" as missing?
        if default_when_none:
            if value is None:
                return default
            elif isinstance(value, six.string_types) and value.lower() == "none":
                return default

        # helper for optional type conversion
        cast_type = lambda value: self._get_type_converter(type, value)(value) if type else value

        # do csv splitting if requested
        if split_csv:
            return [cast_type(v.strip()) for v in brace_expand(value, split_csv=True)]

        return cast_type(value)

    def get_expanded(self, *args, **kwargs):
        """
        Same as :py:meth:`get_default`, but *expandvars* and *expanduser* arguments are set to
        *True* by default.
        """
        kwargs.setdefault("expand_vars", True)
        kwargs.setdefault("expand_user", True)
        return self.get_default(*args, **kwargs)

    def get_expanded_int(self, *args, **kwargs):
        """
        Same as :py:meth:`get_expanded` with *type* set to ``int``.
        """
        kwargs["type"] = int
        return self.get_expanded(*args, **kwargs)

    def get_expanded_float(self, *args, **kwargs):
        """
        Same as :py:meth:`get_expanded` with *type* set to ``float``.
        """
        kwargs["type"] = float
        return self.get_expanded(*args, **kwargs)

    def get_expanded_boolean(self, *args, **kwargs):
        """
        Same as :py:meth:`get_expanded` with *type* set to ``bool``.
        """
        kwargs["type"] = bool
        return self.get_expanded(*args, **kwargs)

    def is_missing_or_none(self, section, option):
        """
        Returns *True* if the value defined by *section* and *option* is missing or ``"None"``
        (case-insensitive), and *False* otherwise. Options without values and those pointing to
        unresolvable references are considered missing. Example:

        .. code-block:: ini

            [my_section]
            a: 123
            b: &::a
            c: &::not_there
            d: None
            e

        .. code-block:: python

            is_missing_or_none("my_section", "a")  # False
            is_missing_or_none("my_section", "b")  # False
            is_missing_or_none("my_section", "c")  # True
            is_missing_or_none("my_section", "d")  # True
            is_missing_or_none("my_section", "e")  # True
            is_missing_or_none("my_section", "f")  # True
        """
        value = self.get_expanded(section, option, default=no_value)
        if isinstance(value, six.string_types):
            value = value.lower()
        return value in ("none", no_value)

    def find_option(self, section, *options):
        """
        Returns the name of the first existing *option* for a given *section*.
        :py:meth:`is_missing_or_none` is used to check the existence. When none of the selected
        *options* exists, *None* is returned.
        """
        for option in options:
            if not self.is_missing_or_none(section, option):
                return option
        return None

    def sync_env(self):
        """
        Synchronizes options defined via environment variables in the format
        ``LAW__<section>__<option>``. The synchronization only works in case neither the section nor
        the option contain double underscores (which is anyway discouraged).
        """
        for name, value in os.environ.items():
            m = self._env_option_regex.match(name)
            if not m:
                continue

            section, option = m.groups()
            if not self.has_section(section):
                self.add_section(section)
            self.set(section, option, value)

    def sync_luigi_config(self, push=True, pull=True):
        """
        Synchronizes sections starting with ``"luigi_"`` with the luigi configuration parser. First,
        when *push* is *True*, (variable-expanded and dereferenced) options that exist in law but
        **not** in luigi are stored as defaults in the luigi config. Then, when *pull* is *True*,
        all luigi-related options in the law config are overwritten with those from luigi. This way,
        options set via luigi defaults (environment variables, global configuration files,
        `LUIGI_CONFIG_PATH`) always have precendence.
        """
        prefix = "luigi_"
        lparser = luigi.configuration.LuigiConfigParser.instance()

        if push:
            for section in self.sections():
                if not section.startswith(prefix):
                    continue
                lsection = section[len(prefix):]

                if not lparser.has_section(lsection):
                    lparser.add_section(lsection)

                for option in self.options(section):
                    if not lparser.has_option(lsection, option):
                        value = self.get_expanded(section, option)
                        lparser.set(lsection, option, value)

        if pull:
            for lsection in lparser.sections():
                section = prefix + lsection

                if not self.has_section(section):
                    self.add_section(section)

                for option, value in lparser.items(lsection):
                    self.set(section, option, value)


# register convenience functions on module-level
for name in __all__[__all__.index("sections"):]:
    def closure(name):
        config = Config.instance()
        func = getattr(config, name)

        def wrapper(*args, **kwargs):
            """
            Shorthand for :py:meth:`Config.{}` of the singleton instance :py:meth:`Config.instance`.
            """
            return func(*args, **kwargs)

        wrapper.__name__ = name
        wrapper.__doc__ = wrapper.__doc__.format(name)

        return wrapper

    locals()[name] = closure(name)


# trailing imports
from law.logger import get_logger

logger = get_logger(__name__)
