module.exports = {
  preset: 'ts-jest',
  testEnvironment: 'node',
  moduleFileExtensions: ['ts', 'tsx', 'js', 'jsx', 'json'],
  moduleNameMapper: {
    '^(\\./.*)\\.js$': '$1',
  },
  testMatch: ['**/tests/server/**/*.test.(ts|js)'],
  testTimeout: 60000,
};
