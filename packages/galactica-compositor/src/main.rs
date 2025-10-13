use anyhow::Result;
use tracing::{info, Level};

#[tokio::main]
async fn main() -> Result<()> {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_max_level(Level::INFO)
        .init();

    info!("🌌 Galactica Compositor v{}", env!("CARGO_PKG_VERSION"));
    info!("Initializing compositor...");

    // TODO: Initialize Wayland compositor
    println!("Compositor not yet implemented - this is a placeholder");

    Ok(())
}