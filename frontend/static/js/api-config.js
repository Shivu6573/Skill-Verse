const localHosts = ["localhost", "127.0.0.1"];
window.SKILLVERSE_API_BASE_URL = window.SKILLVERSE_API_BASE_URL || (
  localHosts.includes(window.location.hostname)
    ? "http://localhost:5000"
    : window.location.origin
);
window.SKILLVERSE_API_URL = (path) => {
  const baseUrl = window.SKILLVERSE_API_BASE_URL.replace(/\/+$/, "");
  return `${baseUrl}${path.startsWith("/") ? path : `/${path}`}`;
};
