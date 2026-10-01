<role>
Senior Python developer following SOLID principles
</role>

<task>
Design modular architecture for a CLI expense tracker application
</task>

<context>
<application_type>Command-line expense tracking and reporting tool</application_type>
<tech_stack>Python 3.8+, CSV file storage, standard library only</tech_stack>
<user_workflow>
1. User runs CLI with expense data file
2. User selects report mode (summary by category, monthly totals, etc.)
3. Application displays formatted report in terminal
</user_workflow>
</context>

<requirements>
<functional>
- Load transaction data from CSV files (date, amount, category, description)
- Support multiple report modes that are easy to add/extend
- Display formatted reports in terminal
- Track totals and provide summaries
- Handle errors gracefully (file not found, invalid data)
</functional>

<architectural>
- Follow SOLID principles explicitly (especially Open/Closed for extensibility)
- Use Strategy pattern for different report types
- Separate concerns: data loading, processing, display
- Each module should be independently testable
- Maximum 200 lines per module
</architectural>
</requirements>

<deliverables>
Provide:
1. High-level architecture with module names and responsibilities
2. Specific design patterns to use and why they fit
3. Module dependency diagram showing data flow
4. File/folder structure
5. Extension points for adding new report types
</deliverables>