DEVICE_TYPE_REGISTRY = {
    "tapo": {
        "label": "Tapo",
        "icon": "plug",
        "config_fields": [
            {"name": "username", "label": "Tapo Username", "type": "email", "required": True, "encrypted": False},
            {"name": "password", "label": "Tapo Password", "type": "password", "required": True, "encrypted": True},
        ],
        "capabilities": ["on", "off", "status"],
        "handler": "devices.handlers.tapo.TapoHandler",
    },
}


def get_device_types():
    """Returns list of device types with their metadata for the frontend."""
    return [
        {
            "id": key,
            "label": val["label"],
            "icon": val["icon"],
            "config_fields": val["config_fields"],
            "capabilities": val["capabilities"],
        }
        for key, val in DEVICE_TYPE_REGISTRY.items()
    ]


def get_handler_class(device_type):
    """Dynamically imports and returns the handler class for a device type."""
    from importlib import import_module
    entry = DEVICE_TYPE_REGISTRY.get(device_type)
    if not entry:
        raise ValueError(f"Unknown device type: {device_type}")
    module_path, class_name = entry["handler"].rsplit(".", 1)
    module = import_module(module_path)
    return getattr(module, class_name)
