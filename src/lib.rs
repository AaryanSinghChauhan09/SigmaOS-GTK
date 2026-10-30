// SPDX-License-Identifier: Apache-2.0
//! SigmaOS-gtk - Linux Mint/Omarchy-inspired component for SigmaOS
//! Part of SigmaOS multi-repository architecture

#![no_std]

/// Cargo package name used to identify this component.
pub const COMPONENT_NAME: &str = env!("CARGO_PKG_NAME");

/// Current implementation maturity; the operational integration is not implemented.
pub const IMPLEMENTATION_STATUS: &str = "scaffold";

/// Component struct
pub struct Component {
    name: &'static str,
}

impl Component {
    pub const fn new() -> Self {
        Self { name: COMPONENT_NAME }
    }

    /// Returns the Cargo package name of this component.
    pub const fn name(&self) -> &'static str {
        self.name
    }

    /// Returns the current implementation maturity.
    pub const fn status(&self) -> &'static str {
        IMPLEMENTATION_STATUS
    }
}

impl Default for Component {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    #[test]
    fn test_creation() {
        let c = super::Component::new();
        assert_eq!(c.name(), env!("CARGO_PKG_NAME"));
        assert_eq!(c.status(), "scaffold");
    }
}
