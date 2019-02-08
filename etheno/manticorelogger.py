# This is a horrible hack that is used to replace manticore.utils.log
# Remove this once https://github.com/trailofbits/manticore/issues/1369
# is resolved.

ETHENO_LOGGER = None

@property
def manticore_verbosity():
    return ETHENO_LOGGER.log_level

@property
def DEFAULT_LOG_LEVEL():
    return ETHENO_LOGGER.log_level

def set_verbosity(setting):
    pass
    #global manticore_verbosity
    #manticore_verbosity = min(max(setting, 0), len(get_levels()) - 1)
    #for logger_name in all_loggers:
    #    logger = logging.getLogger(logger_name)
    #    # min because more verbosity == lower numbers
    #    # This means if you explicitly call setLevel somewhere else in the source, and it's *more*
    #    # verbose, it'll stay that way even if manticore_verbosity is 0.
    #    logger.setLevel(min(get_verbosity(logger_name), logger.getEffectiveLevel()))

all_loggers = set()
