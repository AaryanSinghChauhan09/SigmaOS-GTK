#![forbid(unsafe_code)]
//! GTK native toolkit integration for SigmaOS
use serde::{Deserialize, Serialize};
use thiserror::Error;

#[derive(Debug, Error)]
pub enum ComponentError {
    #[error("entry not found: {0}")]
    NotFound(String),
    #[error("invalid configuration: {0}")]
    InvalidConfig(String),
    #[error("duplicate entry: {0}")]
    AlreadyExists(String),
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
pub enum EntryStatus {
    Ready,
    Running,
    Stopped,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ComponentEntry {
    pub id: String,
    pub label: String,
    pub status: EntryStatus,
    pub tags: Vec<String>,
}

impl ComponentEntry {
    pub fn new(id: &str, label: &str) -> Result<Self, ComponentError> {
        if id.trim().is_empty() {
            return Err(ComponentError::InvalidConfig("id cannot be empty".into()));
        }
        Ok(Self {
            id: id.into(),
            label: label.into(),
            status: EntryStatus::Ready,
            tags: Vec::new(),
        })
    }

    pub fn start(&mut self) {
        self.status = EntryStatus::Running;
    }

    pub fn stop(&mut self) {
        self.status = EntryStatus::Stopped;
    }

    pub fn add_tag(&mut self, tag: &str) {
        if !tag.is_empty() {
            self.tags.push(tag.into());
        }
    }
}

pub struct ComponentRegistry {
    entries: Vec<ComponentEntry>,
}

impl ComponentRegistry {
    pub fn new() -> Self {
        Self { entries: Vec::new() }
    }

    pub fn register(&mut self, entry: ComponentEntry) -> Result<(), ComponentError> {
        if self.entries.iter().any(|e| e.id == entry.id) {
            return Err(ComponentError::AlreadyExists(entry.id));
        }
        self.entries.push(entry);
        Ok(())
    }

    pub fn get(&self, id: &str) -> Result<&ComponentEntry, ComponentError> {
        self.entries
            .iter()
            .find(|e| e.id == id)
            .ok_or_else(|| ComponentError::NotFound(id.into()))
    }

    pub fn running_count(&self) -> usize {
        self.entries.iter().filter(|e| e.status == EntryStatus::Running).count()
    }
}

impl Default for ComponentRegistry {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_register_and_get_aaa() {
        // Arrange
        let mut reg = ComponentRegistry::new();
        let entry = ComponentEntry::new("item-1", "Primary Item").unwrap();

        // Act
        reg.register(entry).unwrap();

        // Assert
        assert_eq!(reg.get("item-1").unwrap().label, "Primary Item");
    }

    #[test]
    fn test_status_lifecycle_aaa() {
        // Arrange
        let mut reg = ComponentRegistry::new();
        let mut entry = ComponentEntry::new("svc-1", "Service").unwrap();
        entry.start();
        reg.register(entry).unwrap();

        // Act
        let running = reg.running_count();

        // Assert
        assert_eq!(running, 1);
    }

    #[test]
    fn test_duplicate_entry_aaa() {
        // Arrange
        let mut reg = ComponentRegistry::new();
        reg.register(ComponentEntry::new("dup", "First").unwrap()).unwrap();

        // Act
        let res = reg.register(ComponentEntry::new("dup", "Second").unwrap());

        // Assert
        assert!(matches!(res, Err(ComponentError::AlreadyExists(_))));
    }

    #[test]
    fn test_invalid_empty_id_aaa() {
        // Arrange / Act
        let res = ComponentEntry::new("", "Invalid");

        // Assert
        assert!(matches!(res, Err(ComponentError::InvalidConfig(_))));
    }
}
