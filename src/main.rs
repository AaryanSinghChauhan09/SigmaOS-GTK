use clap::Parser;
use gtk::gtk;

#[derive(Parser)]
struct Cli;

fn main() -> anyhow::Result<()> {
    let config = gtk::Config::default();
    let mut component = gtk::new(config);
    component.initialize()?;
    println!("SigmaOS-gtk ready");
    Ok(())
}
