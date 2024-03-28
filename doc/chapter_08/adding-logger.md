# Adding separate loggers instead of project-wide debug level

kdesrc-build (predecessor of kde-builder) used one debug level for the whole project. This is very inconvenient.
When you want to debug just one package (a perl term, means module in python terms), you have to watch the debug logs from every other packages (modules), which you may not be interested in.

Python provides a built-in `logging` module, and we can use separate loggers for separate things.

Here is how we add a new logger to the project.

Add logger to the `data/kde-builder-logging.yaml`.

```yaml
loggers:
  ksblib.DependencyResolver:
    level: INFO
    ...
```

set the level to `INFO` (the default level used in kdesrc-build). The user could edit the level to `DEBUG` if he wants.

Then in the python module, import the logging module:
```
import logging
```

Then create a logger:
```
logger = logging.getLogger(__name__)
```

Replace the perl's project-wide debug messages approach, such as:
```
Debug().error(f"r[Invalid dependency declaration: b[{dep}]]")
```

with the logger message of corresponding level, while still using `Debug().colorize` function:
```
logger.error(Debug().colorize(f"r[Invalid dependency declaration: b[{dep}]]"))
```

The `Debug().note()` are needed to be considered as `Debug().warning()`,  
and `Debug().whisper()` as `Debug().debug()`.

This is a table of log levels that will be achieved with that conversion: 

|   Original (perl) levels    | Python logger levels |
|:---------------------------:|:--------------------:|
|                             |    CRITICAL (50)     |
|          ERROR (5)          |      ERROR (40)      |
| WARNING (4) <br/> NOTE (3)  |     WARNING (30)     |
|          INFO (2)           |      INFO (20)       |
| WHISPER (1) <br/> DEBUG (0) |      DEBUG (10)      |
|                             |      NOTSET (0)      |

See [](#changing-verbosity) for the used command line options.
