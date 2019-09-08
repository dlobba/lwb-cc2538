TESTBED_TEMPLATE = \
r"""
{
    "name" : "Glossy Test",
    "description" : "Run Glossy for {{ duration_minutes }} minutes",
    "ts_init" : "{{ ts_init }}",
    "duration" : {{ duration_seconds }},
    "image" : {
        "hardware" : "firefly",
        "file":    "< path-to-binary >",
        "programAddress": "0x00200000",
        "target":  "< list-of-targets >"
    }
}
"""
