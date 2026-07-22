// Erzwingt das vereinbarte Commit-Schema:
//   feat(scope): ...  -> MINOR
//   fix(scope): ...   -> PATCH
//   feat!: ...        -> MAJOR (reserviert für v1.0.0)
//   chore/docs/ci/test -> kein Release
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      ['feat', 'fix', 'chore', 'docs', 'ci', 'test', 'refactor', 'perf', 'style']
    ],
    'scope-enum': [
      2,
      'always',
      [
        'auth', 'receipts', 'buckets', 'pricing', 'documents', 'audit',
        'monitoring', 'logs', 'services', 'dashboard', 'api', 'db', 'ui',
        'docker', 'ci', 'deps', 'release', 'readme', 'license', 'security',
        'notifications'
      ]
    ],
    'scope-empty': [2, 'never'],
    'subject-case': [0]
  }
};
