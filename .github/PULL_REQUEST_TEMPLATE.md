name: Pull Request

description: Submit changes to dbt Lens
title: "[PR] "
labels: []
assignees: []

body:
  - type: markdown
    attributes:
      value: |
        ## Pull Request Checklist

        Thanks for contributing to dbt Lens! Please fill out the checklist below.

  - type: checkboxes
    id: checklist
    attributes:
      label: "Checklist"
      options:
        - label: "I tested my changes locally with `streamlit run app.py`"
          value: tested
        - label: "I clicked 'Load example project' and the score still works"
          value: example-works
        - label: "I added no new `print()` statements"
          value: no-print
        - label: "My code follows the existing style (PEP 8, snake_case)"
          value: style
        - label: "I updated CHANGELOG.md if this is a new feature"
          value: changelog

  - type: textarea
    id: description
    attributes:
      label: "Description"
      description: "What did you change and why?"
      placeholder: |
        ## What changed

        Brief description of the change.

        ## Why

        The reason for this change.

        ## Testing

        How you verified it works.
    validations:
      required: true

  - type: input
    id: issue
    attributes:
      label: "Related GitHub Issue (optional)"
      description: "Paste the issue number if this PR fixes one (e.g. #42)"
      placeholder: "#42"