const {withEsbuildOverride} = require('remix-esbuild-override');
const GlobalsPolyfills = require('@esbuild-plugins/node-globals-polyfill').default;

withEsbuildOverride((option, {isServer}) => {
  if (isServer) {
    option.plugins = [
      GlobalsPolyfills({
        process: 'process/browser',
      }),
      ...option.plugins,
    ];
  }
  return option;
});

module.exports = {
  appDirectory: 'app',
  assetsBuildDirectory: 'public/build',
  ignoredRouteFiles: ['**/.*'],
  publicPath: '/build/',
  serverBuildPath: 'build/index.js',
  serverBuildTarget: 'node-cjs',
  serverDependenciesToBundle: ['copy-text-to-clipboard'],
};
