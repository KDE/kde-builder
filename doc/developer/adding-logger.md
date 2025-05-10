# Project loggers

## Creating and using specific logger

Python provides a built-in `logging` module, and we can use separate loggers for separate things.

Here is how we add a new logger to the project.

Add logger to the `data/kde-builder-logging.yaml`. For example:
```yaml
loggers:
  resolving-dependencies:
    level: INFO
    ...
```

set the level to `INFO` (the default level used in kdesrc-build). The user could edit the level to `DEBUG` if he/she wants.

```{note}
See [](#changing-verbosity) for the user documentation on changing verbosity level.
```

Then in the python module, import the `kbLogger` module:
```python
from Debug import kbLogger
```

Then create a logger:
```python
logger_res_deps = kbLogger.getLogger("resolving-dependencies")
```

After that, you can use it as normal `logging.Logger` logger, for example:
```python
logger_res_deps.debug("Starting resolving dependencies for kcalc:")
```

## Replaced perl project-wide logger with separate loggers

kdesrc-build (predecessor of kde-builder) used one debug level for the whole project. This is very inconvenient.
When you want to debug just one aspect of output, for example, the variables used when running build process, you have to see
the debug logs from every other aspects, such as dependency resolution, which is very long, and you may not be interested in it.

So the original perl's project loggers were reworked.

Global log messages, that were appeared like this:
```python
Debug().error(f"r[Invalid dependency declaration: b[{dep}]]")
```

were assigned to specific loggers, with the corresponding severity level:
```python
logger_res_deps.error(f"r[Invalid dependency declaration: b[{dep}]]")
```

Note that colorizing (the elements like `r[` and `]`) still can be used.

The `Debug().note()` statements were considered as `Debug().warning()`,  
and the `Debug().whisper()` and `Debug().pretend()` statements were considered as `Debug().debug()`.

This is a table of log levels that was used with that conversion: 

|  Original (perl) levels <br/> and their cli options   | Python logger levels |
|:-----------------------------------------------------:|:--------------------:|
|                                                       |    CRITICAL (50)     |
|             ERROR (5) `Always was shown`              |      ERROR (40)      |
| WARNING (4) `--really-quiet` <br/> NOTE (3) `--quiet` |     WARNING (30)     |
|            INFO (2) `Selected by default`             |      INFO (20)       |
|   WHISPER (1) `--verbose` <br/> DEBUG (0) `--debug`   |      DEBUG (10)      |
|                                                       |      NOTSET (0)      |
