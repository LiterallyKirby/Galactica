project('galium-vanilla', 'c', version: '0.1.0', default_options: [
  'c_std=c11',
  'warning_level=3',
  'optimization=2',
])

wayland = dependency('wayland-server', required: true)
pixman = dependency('pixman-1', required: true)
xkbcommon = dependency('xkbcommon', required: true)

# Hardening flags
add_project_arguments(
  '-fstack-protector-strong',
  '-D_FORTIFY_SOURCE=2',
  '-fPIE',
  '-fvisibility=hidden',
  '-Wformat',
  '-Wformat-security',
  language: 'c'
)

add_project_link_arguments(
  '-Wl,-z,relro',
  '-Wl,-z,now',
  '-Wl,--as-needed',
  '-Wl,--gc-sections',
  '-pie',
  language: 'c'
)

sources = [
  'src/main.c',
  'src/security.c',
  'src/compositor.c',
  'src/renderer.c',
  'src/output.c',
  'src/shm.c',
]

executable(
  'galium-vanilla',
  sources,
  dependencies: [wayland, pixman, xkbcommon],
  include_directories: include_directories('include'),
  install: false
)
