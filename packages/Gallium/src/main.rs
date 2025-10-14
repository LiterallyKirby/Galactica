use anyhow::Result;
use smithay::reexports::calloop::{EventLoop, LoopSignal};
use tracing::{info, Level};
use tracing_subscriber::FmtSubscriber;
use glow::HasContext;
use std::env;
use std::rc::Rc;
use std::cell::RefCell;

fn main() -> Result<()> {
    // Setup logging
    let subscriber = FmtSubscriber::builder()
        .with_max_level(Level::INFO)
        .finish();
    tracing::subscriber::set_global_default(subscriber)
        .expect("setting default subscriber failed");

    info!("🚀 Gallium compositor starting...");

    // Verify llvmpipe env vars
    let gallium_driver = env::var("GALLIUM_DRIVER").unwrap_or_else(|_| "not set".into());
    let libgl_sw = env::var("LIBGL_ALWAYS_SOFTWARE").unwrap_or_else(|_| "not set".into());
    info!("Environment: GALLIUM_DRIVER={}, LIBGL_ALWAYS_SOFTWARE={}", gallium_driver, libgl_sw);

    // Initialize event loop
    let mut event_loop: EventLoop<()> = EventLoop::try_new().unwrap();
    let signal: LoopSignal = event_loop.get_signal();
    let signal_rc = Rc::new(RefCell::new(signal));

    // Initialize a headless GL context (software-rendered)
    unsafe {
        let gl = glow::Context::from_loader_function(|s| {
            smithay::reexports::glutin::platform::unix::HeadlessContext::new().unwrap().get_proc_address(s)
        });
        info!("Initialized OpenGL context: {:?}", gl);
    }

    info!("✅ Gallium compositor initialized successfully. Using llvmpipe if configured.");
    info!("Press Ctrl+C to exit.");

    // Run the event loop
    event_loop.run(None, &mut (), |_| {})?;

    Ok(())
}
