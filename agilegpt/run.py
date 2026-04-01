import logging
from orchestrator.fsm_orchestrator import FSMOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")

orch = FSMOrchestrator()

# Progress callback — prints each FSM phase as it starts.
orch.on_progress = lambda phase, msg: print(f"\n{'='*60}\n[{phase}] {msg}\n{'='*60}")

story = """The client is Code2040.

Their mission: To activate, connect, and mobilize the largest racial equity community in tech to dismantle the structural barriers that prevent full participation and leadership of Black and Latinx technologists.

Their vision: A tech industry that reflects the diversity of the United States, where Black and Latinx people are fully represented as leaders, founders, investors, and innovators at every level.

About them: Code2040 is a nonprofit that creates pathways for Black and Latinx technologists to access, excel in, and lead in the innovation economy. Founded in 2012, the organization runs intensive fellowship and residency programs that place early-career engineers at top tech companies, provides professional development and mentorship, and partners with companies to improve their hiring and retention practices. Code2040 also produces research on racial equity in tech and advocates for systemic change across the industry. The organization has built a community of over 5,000 alumni who are now engineers, founders, and leaders at companies from startups to Fortune 500s.

They primarily serve: Black and Latinx college students and early-career technologists, tech companies seeking to diversify their engineering teams, university computer science programs, and corporate diversity & inclusion leaders.

Core values: Racial equity as a north star, Community over competition, Transparency and accountability, Excellence through inclusion, Bold action over incremental change, Celebrating Black and Latinx brilliance, Data-driven advocacy.

Brand tone: Bold, empowering, warm, and unapologetically focused on racial equity — blending professional credibility with authentic community voice and celebration of culture.

Key programs/services:
  - Fellows Program: An intensive summer internship program that matches Black and Latinx CS students with top tech companies, providing technical training, professional development workshops, executive mentorship, and community support throughout the experience.
  - Residency Program: A nine-month program for early-career engineers transitioning into their first full-time roles, offering peer cohorts, leadership coaching, and ongoing skill development to accelerate their careers.
  - Tech Company Partnerships: Code2040 works directly with companies to audit their hiring pipelines, train managers on inclusive leadership, and build retention strategies that keep diverse talent engaged and advancing.
  - Alumni Network: A 5,000+ member community of Code2040 graduates who mentor current participants, collaborate on ventures, and serve as a talent pipeline for partner companies.

Impact stats:
  - Alumni in the Code2040 network: 5,200+
  - Tech companies partnered with: 85
  - Fellows placed at top companies since founding: 1,400+
  - Average salary increase for Fellows within 2 years: 42%
  - Alumni who are now engineering managers or directors: 340
  - Alumni-founded startups: 78
  - Universities represented in programs: 120+
  - Retention rate of Fellows at host companies (2+ years): 89%

Leadership:
  - Karla Monterroso (former CEO, Board Advisor)
  - Mimi Fox Melton (CEO)
  - James Norman (Board Chair)
  - Dr. Allison Scott (VP of Research)
  - Marcus Johnson (Director of Fellows Program)
  - Sofia Ramirez (Director of Partnerships)

Events: Annual Code2040 Summit, Fellows Demo Day, Tech Equity Conference, monthly Alumni Fireside Chats.

Partners: Google, Lyft, Dropbox, Salesforce, Twilio, Spotify, Asana, Uber, Capital One, JPMorgan Chase.

Financials note: Code2040 is funded through a combination of tech company partnerships, foundation grants from the Kapor Center, Ford Foundation, and Knight Foundation, and individual donors committed to racial equity in technology.

Current website: https://www.code2040.org.

Suggested website pages beyond Home & About Us:
  - Programs: To detail the Fellows Program, Residency Program, and Alumni Network with application timelines, eligibility, and testimonials from past participants.
  - For Companies: To showcase partnership opportunities, company training services, and case studies of improved hiring outcomes at partner organizations.
  - Impact & Data: To present alumni outcomes, diversity metrics, research reports, and an interactive data dashboard showing the pipeline's growth over time.
  - Community: To highlight alumni stories, upcoming events, mentorship opportunities, and a blog featuring perspectives from the Code2040 network.
"""

state = orch.run_pipeline("code2040", story)

print(f"\n{'='*60}")
print(f"Pipeline complete!")
print(f"FSM Phase: {state.fsm_phase}")
print(f"Total sprints: {state.total_sprints}")
print(f"Workspace: {state.workspace_path}")
print(f"Completed states: {state.completed_states}")
if state.site_url:
    print(f"\nYour site is live at: {state.site_url}")
print(f"{'='*60}")
