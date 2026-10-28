// SPDX-License-Identifier: Apache-2.0
//! SigmaOS-gtk - Linux Mint/Omarchy-inspired component for SigmaOS
//! Part of SigmaOS multi-repository architecture

#![no_std]

/// Component struct
pub struct Component {
    name: &'static str,
}

impl Component {
    pub fn new() -> Self {
        Self { name: "SigmaOS Component" }
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
        assert_eq!(c.name, "SigmaOS Component");
    }
}
