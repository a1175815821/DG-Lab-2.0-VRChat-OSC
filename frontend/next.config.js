module.exports = {
  reactStrictMode: true,
  async rewrites () {
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:38080/api/:path*' // Proxy to Backend
      }
    ]
  }
};