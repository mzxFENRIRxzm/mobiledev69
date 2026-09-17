{{flutter_js}}
{{flutter_build_config}}

// This app requires its API; do not register an offline service worker that
// could keep an older UI paired with a newer API. Startup retires older workers.
_flutter.loader.load();
