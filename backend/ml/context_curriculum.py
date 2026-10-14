"""Build auditable duty, background and mixed-duty training examples.

These examples are project-authored, not scraped vacancies or expert labels.
Each core duty and all its contextual variants stay in one split. Development
uses different duties and different background templates from training.
"""

import argparse
import json
from pathlib import Path
import random

from backend.ml.context_data import load_cases

# The last three duties in each group are development examples. Keep the
# assignment fixed; do not move examples after looking at model predictions.
DUTIES = {
    'Programming': [
        'Implement the subscription renewal logic in the billing application.',
        'Create reusable functions for importing records into our software.',
        'Replace duplicated source code with smaller maintainable modules.',
        'Build the interactive controls that let visitors edit their shopping cart.',
        'Turn the product specification into a working mobile application.',
        'Extend the existing service with new endpoints and business logic.',
        'Give the legacy code a new lease of life by rewriting its slow routines.',
        'Construct browser widgets that work across desktop and mobile devices.',
        'Make the computer do the boring part by writing a script to process invoices.',
        'Implement the messaging feature in our collaboration platform.',
        'Develop a library that converts incoming sensor readings into application objects.',
        'Write the source code that connects the booking form to the reservation service.',
    ],
    'Debugging': [
        'Trace the stack exception to the faulty function and correct its implementation.',
        'Investigate why the application hangs when two requests arrive together.',
        'Find and repair the race condition causing duplicate database writes.',
        'Follow the breadcrumbs in the error logs until you identify the software defect.',
        'Diagnose the memory leak and fix the component responsible for it.',
        'Work out why the upload code rejects valid files and repair the defect.',
        'Untangle the exception chain that makes the payment service crash.',
        'Locate the broken calculation in the pricing module and correct it.',
        'Hunt down the bug hiding behind the occasional blank screen.',
        'Identify the code path responsible for a failed login and implement a repair.',
        'Investigate inconsistent application results and isolate the faulty expression.',
        'Use diagnostic traces to find why the background worker stops unexpectedly.',
    ],
    'Software testing': [
        'Write automated checks for expected behaviour before a feature is released.',
        'Verify that invalid form inputs produce the expected validation messages.',
        'Run regression scenarios after each change to the billing system.',
        'Check acceptance criteria against the application and document failures.',
        'Try boundary values and unusual user sequences to uncover software defects.',
        'Create a repeatable test suite for the reservation workflow.',
        'Be the awkward user on purpose and check how the software handles mistakes.',
        'Validate the patch against both normal and unusual application inputs.',
        'Make broken builds earn their rejection with automated verification checks.',
        'Exercise the new search feature with empty, duplicate and malformed queries.',
        'Compare actual software behaviour with the written acceptance scenarios.',
        'Add automated regression coverage for previously reported application failures.',
    ],
    'Interface design': [
        'Arrange the screen controls so visitors can find their next action easily.',
        'Improve the visual hierarchy of the checkout page.',
        'Create wireframes for a more understandable account settings screen.',
        'Refine the navigation layout after observing where users get lost.',
        'Choose spacing and typography that make the dashboard easier to scan.',
        'Reshape the registration form to make the required steps clearer.',
        'Rescue the website from its wall of buttons with a simpler layout.',
        'Design consistent visual states for selected, disabled and focused controls.',
        'Give confusing menus a makeover so users can actually find the settings.',
        'Revise the mobile page layout to make the primary action easier to reach.',
        'Design the visual arrangement of the new reporting screen.',
        'Develop an intuitive navigation structure for the customer portal.',
    ],
    'Deployment': [
        'Roll out approved application releases and monitor service health afterward.',
        'Restore the previous software version when a release causes an outage.',
        'Keep production services running and respond to availability alerts.',
        'Manage the pipeline that publishes application builds into production.',
        'Plan safe software rollouts with a working rollback procedure.',
        'Bring the service back online after a failed infrastructure change.',
        'Keep the lights on for the application when a rollout goes sideways.',
        'Operate the release process across staging and production environments.',
        'Get the application back on its feet after an availability incident.',
        'Monitor live service availability during a staged release.',
        'Publish verified builds and check that the running service remains healthy.',
        'Recover the production application when an update interrupts service.',
    ],
    'Data analysis': [
        'Compare revenue trends across regions and explain the differences.',
        'Examine survey results to identify patterns in customer responses.',
        'Calculate conversion rates and interpret changes over time.',
        'Use transaction records to investigate an unexpected rise in refunds.',
        'Assess which distribution channels perform best using the available figures.',
        'Turn a table of experiment results into conclusions supported by the numbers.',
        'Make sense of the numerical spaghetti in our weekly performance reports.',
        'Compare staffing scenarios using historical demand and productivity figures.',
        'Tell us what the charts mean after the decorative arrows are removed.',
        'Examine regional attendance figures and identify meaningful changes.',
        'Interpret the relationship between delivery delays and return rates.',
        'Use measured outcomes to compare the performance of two service approaches.',
    ],
    'Marketing communication': [
        'Explain the product benefits in messages aimed at prospective buyers.',
        'Write persuasive campaign copy that gives customers a reason to try the service.',
        'Adapt the brand story to appeal to a new audience.',
        'Develop promotional messaging that makes our offering understandable and appealing.',
        'Turn technical product features into convincing customer benefits.',
        'Prepare the value proposition used in sales proposals.',
        'Make our ordinary storage boxes sound useful through an honest compelling product story.',
        'Give prospective clients a clear reason to choose our product.',
        'Translate the brochure buzzwords into benefits a buyer would care about.',
        'Create persuasive messaging for the launch of a subscription service.',
        'Describe the commercial value of a product in a customer proposal.',
        'Position the offering with a clear message for potential business customers.',
    ],
    'Social media communication': [
        'Publish engaging updates on the brand social accounts.',
        'Prepare posts that encourage discussion among our online followers.',
        'Respond to audience comments across the company social channels.',
        'Adapt product news into content suitable for social networks.',
        'Manage the schedule of posts for our online community.',
        'Create short social updates and engage with the people responding to them.',
        'Keep the brand feed alive with posts people might actually want to read.',
        'Write captions and share updates with followers on our social pages.',
        'Give the company timeline something more interesting than another stock photo.',
        'Publish useful community posts and reply to discussion threads.',
        'Create a consistent stream of engaging social-network content.',
        'Manage conversations with followers through the official brand accounts.',
    ],
    'Presentation': [
        'Explain the quarterly results to stakeholders using a clear slide deck.',
        'Deliver a short talk that introduces the new service to partners.',
        'Prepare visual slides and present the project findings to the leadership group.',
        'Turn a technical report into an understandable talk for a general audience.',
        'Present progress updates clearly during client meetings.',
        'Organise the main points of a talk and explain them confidently to an audience.',
        'Give the board a presentation that survives beyond the title slide.',
        'Create a deck that helps an audience follow the recommended approach.',
        'Bring order to the slide avalanche and deliver a coherent project update.',
        'Present the annual findings to a room of external partners.',
        'Use clear visuals to explain an unfamiliar concept during a public talk.',
        'Prepare and deliver a concise demonstration for a stakeholder audience.',
    ],
    'Customer support': [
        'Help subscribers resolve problems with their account access.',
        'Answer customer questions about using the purchased service.',
        'Guide a caller through the steps needed to restore their settings.',
        'Resolve customer complaints about missing deliveries and incorrect orders.',
        'Provide practical help when a user cannot complete a purchase.',
        'Explain how customers can fix common problems with the device.',
        'Rescue users from the settings maze when they contact the help desk.',
        'Handle service requests and follow through until the customer issue is resolved.',
        'Be the calm voice when a customer insists their account has vanished.',
        'Assist members who are unable to activate their subscription.',
        'Respond to service enquiries and help clients use the product successfully.',
        'Walk customers through resolving common configuration problems.',
    ],
    'Written communication': [
        'Write clear instructions explaining how to complete the process.',
        'Prepare concise professional emails that explain decisions and next steps.',
        'Edit the user guide so readers can understand each written instruction.',
        'Translate technical jargon into plain language in the documentation.',
        'Draft an accurate report with a structure that readers can follow.',
        'Adapt the wording of a difficult message to suit its recipient.',
        'Turn a mountain of acronyms into a readable instruction sheet.',
        'Write courteous replies that make the action required from the reader clear.',
        'Make our documentation readable by people who were absent from the meeting.',
        'Explain a policy change in a clear written notice.',
        'Compose a precise summary that colleagues can use without further explanation.',
        'Rewrite confusing instructions using simple and consistent language.',
    ],
    'Empathy': [
        'Acknowledge the feelings of an upset person and respond with patience.',
        'Recognise why a customer is frustrated and show understanding.',
        'Support a distressed colleague with care and consideration.',
        'Respond sensitively when someone shares a difficult personal experience.',
        'Consider how a decision affects the people receiving the news.',
        'Make a worried caller feel understood rather than dismissed.',
        'Keep your human side switched on when someone arrives upset.',
        'Show compassion toward people struggling with an unfamiliar situation.',
        'Take the frustration of another person seriously even when the queue is long.',
        'Respond with understanding to someone who feels excluded.',
        'Recognise the emotional perspective of another person before responding.',
        'Offer patient and considerate support to a person who is anxious.',
    ],
    'Conflict resolution': [
        'Help two departments settle a disagreement over shared responsibilities.',
        'Mediate a dispute between colleagues and find a workable resolution.',
        'Bring opposing viewpoints together so a team can resolve its conflict.',
        'Defuse tension between project groups and help them agree how to proceed.',
        'Facilitate a constructive discussion when colleagues are arguing.',
        'Work through a disagreement until the parties can accept a common solution.',
        'Lower the temperature when a team discussion turns into a battle.',
        'Help competing departments resolve the dispute blocking their work.',
        'Turn a workplace shouting match into an agreement everyone can act on.',
        'Resolve a disagreement between two partners about project responsibilities.',
        'Help colleagues reconcile opposing views during a difficult dispute.',
        'Mediate the conflict preventing two groups from working together.',
    ],
    'Teamwork': [
        'Coordinate the work with colleagues from several departments.',
        'Share information with partner teams to deliver the agreed project.',
        'Work alongside colleagues on tasks that contribute to a common outcome.',
        'Collaborate with finance and operations to complete the shared assignment.',
        'Keep other team members informed and cooperate on the handover.',
        'Combine your work with colleagues contributions to deliver the final result.',
        'Keep the relay baton moving between departments instead of dropping it.',
        'Work closely with the engineering group and exchange information regularly.',
        'Get the separate teams rowing in the same direction on shared tasks.',
        'Partner with colleagues in another office to complete a joint deliverable.',
        'Contribute to the group task and support the other members doing their part.',
        'Coordinate responsibilities with the people sharing the same project goal.',
    ],
    'Active listening': [
        'Listen carefully to the caller and clarify what they mean before responding.',
        'Ask follow-up questions to check that you understood the concern.',
        'Give people room to explain their needs and confirm your understanding.',
        'Summarise what the other person said to verify you heard it correctly.',
        'Pay attention during discussions and clarify ambiguous requests.',
        'Hear the full explanation before deciding what the person needs.',
        'Let the other person finish instead of mentally writing your reply.',
        'Check your understanding by repeating the main concern in your own words.',
        'Keep both ears open when a stakeholder explains an unfamiliar problem.',
        'Listen to the request and ask specific questions about unclear details.',
        'Confirm the speaker intended meaning before proposing a response.',
        'Give the customer your attention and verify you understood their priorities.',
    ],
    'Time management': [
        'Decide which tasks to handle first when several deadlines compete.',
        'Organise the daily workload so urgent and routine assignments finish on time.',
        'Balance interruptions with the work already due that afternoon.',
        'Allocate your time across several responsibilities with fixed deadlines.',
        'Prioritise incoming requests according to urgency and available time.',
        'Keep track of due dates and schedule your own work accordingly.',
        'Keep the deadline queue moving before it becomes a traffic jam.',
        'Fit changing requests into your workload while protecting important deadlines.',
        'Juggle competing tasks without letting the urgent work hit the floor.',
        'Plan the order of your daily assignments to meet their different due dates.',
        'Manage competing demands on your time during a busy reporting period.',
        'Choose priorities sensibly when several urgent assignments arrive together.',
    ],
    'Attention to detail': [
        'Check the invoice entries carefully for small inconsistencies.',
        'Verify that every required field in the records is complete and accurate.',
        'Spot errors in the figures before the report is submitted.',
        'Compare the document against the source records to catch omissions.',
        'Proofread the final files and correct inconsistent names or dates.',
        'Maintain accurate records by checking each entry against the original.',
        'Catch the decimal point that has wandered into the wrong place.',
        'Inspect the submitted forms for missing information and transcription mistakes.',
        'Be the person who notices the tiny discrepancy before it becomes expensive.',
        'Check that the inventory records exactly match the approved changes.',
        'Review the application forms carefully for incomplete or inconsistent details.',
        'Verify small differences between the purchase order and the delivered quantities.',
    ],
    'Problem solving': [
        'Identify the cause of an operational difficulty and compare practical remedies.',
        'Work out why the process is failing and choose a feasible way to improve it.',
        'Break an unfamiliar problem into parts and investigate possible solutions.',
        'Consider several approaches before selecting a way around the obstacle.',
        'Use the available evidence to decide how to resolve the recurring issue.',
        'Find a workable alternative when the usual process cannot be followed.',
        'Untie the operational knot instead of adding another workaround to it.',
        'Assess the underlying difficulty and test practical ways of addressing it.',
        'Turn an impossible-looking task into a set of solvable questions.',
        'Evaluate possible causes of the bottleneck and choose an effective remedy.',
        'Identify a practical solution when the agreed process runs into an obstacle.',
        'Compare the trade-offs of different ways to resolve the service difficulty.',
    ],
    'Teaching': [
        'Demonstrate the procedure to apprentices and help them practise it.',
        'Explain a new concept to trainees using examples they can understand.',
        'Coach a new colleague through the steps of an unfamiliar workflow.',
        'Prepare a lesson that helps learners understand the underlying principles.',
        'Give junior staff feedback that helps them develop their skills.',
        'Guide workshop participants through a practical exercise.',
        'Make the unfamiliar tool less mysterious by showing new hires how it works.',
        'Help a colleague learn the method through explanation and supervised practice.',
        'Turn the onboarding maze into a process a new starter can learn.',
        'Explain the procedure to students and check their understanding with an exercise.',
        'Mentor a trainee by demonstrating techniques and reviewing their practice.',
        'Help inexperienced colleagues develop their knowledge of the new process.',
    ],
    'Negotiation': [
        'Agree supplier prices and delivery conditions that both parties can accept.',
        'Discuss contract terms with the client and reach a workable agreement.',
        'Reconcile competing commercial interests during a purchasing discussion.',
        'Work with vendors to settle the scope and cost of the proposed contract.',
        'Find acceptable terms when a supplier requests changes to an agreement.',
        'Discuss alternatives with the buyer to reach a mutually acceptable deal.',
        'Bring the price discussion back to earth and agree terms with the supplier.',
        'Resolve differences over contract conditions through a constructive bargaining process.',
        'Keep the deal moving while both sides debate the small print.',
        'Reach agreement on the delivery schedule and payment terms with a vendor.',
        'Discuss competing contract proposals and settle on terms acceptable to both sides.',
        'Work through the changes requested by the client to arrive at an agreed commercial offer.',
    ],
    'Planning': [
        'Define project milestones and allocate the resources needed to reach them.',
        'Set up the schedule, budget and responsibilities for the upcoming event.',
        'Break the programme into tasks and track progress toward its goals.',
        'Prepare the delivery plan and identify dependencies between activities.',
        'Coordinate the timeline and resource allocation for the service launch.',
        'Organise the work needed to complete the project within its agreed scope.',
        'Give the project a route map before everyone starts driving in different directions.',
        'Plan the event suppliers, staffing needs and delivery milestones.',
        'Build a sensible project schedule out of the pile of enthusiastic promises.',
        'Establish the annual programme priorities and a schedule for carrying them out.',
        'Prepare a resource plan and monitor progress against the project milestones.',
        'Organise the activities and budget needed for the upcoming community event.',
    ],
    'Research': [
        'Investigate the question using reliable publications and primary sources.',
        'Compare available evidence before drawing conclusions about the proposed approach.',
        'Find trustworthy information about unfamiliar methods and summarise what you learn.',
        'Review relevant studies to establish what is already known about the issue.',
        'Gather evidence from several sources and assess its reliability.',
        'Stay informed about new developments by investigating credible technical material.',
        'Separate useful evidence from the internet noise before recommending an approach.',
        'Explore the available literature to answer the project question.',
        'Follow the evidence trail instead of trusting the loudest headline.',
        'Examine published findings to understand recent developments in the field.',
        'Locate credible sources that help answer a specific operational question.',
        'Investigate alternative methods and compare the quality of the supporting evidence.',
    ],
    'Adaptability': [
        'Adjust your approach when the project priorities change.',
        'Learn an unfamiliar workflow when the team adopts a new process.',
        'Switch between different responsibilities as the needs of the role evolve.',
        'Respond constructively when new information changes the agreed approach.',
        'Become comfortable with unfamiliar tools when the work requires them.',
        'Modify your routine to handle a new operating environment.',
        'Change gears when the carefully arranged plan meets reality.',
        'Take on unfamiliar tasks and learn how to perform them as priorities shift.',
        'Keep your balance when the role changes shape halfway through the week.',
        'Adjust to a revised process while continuing to deliver useful work.',
        'Learn new responsibilities when the organisation changes its operating model.',
        'Respond effectively when the assignment requires a different approach than expected.',
    ],
    'Persistence': [
        'Keep working toward the goal after an initial attempt fails.',
        'Follow through on difficult tasks despite repeated setbacks.',
        'Maintain sustained effort when progress is slower than expected.',
        'Continue trying practical approaches instead of abandoning a challenging assignment.',
        'Stay committed to completing the work when obstacles arise.',
        'Keep making progress through a long and demanding project.',
        'Stick with the task after the easy enthusiasm has worn off.',
        'Carry the assignment through to completion despite unexpected difficulties.',
        'Keep going when the first promising solution turns out to be a dead end.',
        'Sustain the effort needed to finish a demanding piece of work.',
        'Continue pursuing the agreed goal after an unsuccessful attempt.',
        'Follow through with consistent effort when the project becomes challenging.',
    ],
}


def build(output):
    rows=[]
    positive={'train':[],'dev':[]}
    for label,duties in DUTIES.items():
        for index,duty in enumerate(duties):
            split='train' if index<9 else 'dev'
            family=f'curriculum-{label.lower().replace(" ","-")}-{index}'
            def add(suffix,text,expected):
                rows.append({'id':family+'-'+suffix,'family':family,'split':split,
                    'origin':'project-authored-curriculum','text':text,'expected':expected,'acceptable':[]})
            add('duty',duty,[label])
            positive[split].append((duty,label,family))
            if split=='train':
                add('benefit',f'An optional staff course is advertised as: "{duty}" This describes a perk, not work assigned to this role.',[])
                add('quotation',f'A comedy sketch about office life includes the line "{duty}" The sketch is entertainment rather than a vacancy.',[])
                add('provider',f'The employer offers new recruits instruction on how to {duty[0].lower()+duty[1:]} This is provided training, not a responsibility to teach others.',[])
            else:
                add('benefit',f'The perks brochure lists a voluntary workshop: "{duty}" Attendance is optional and unrelated to assigned duties.',[])
                add('quotation',f'A former worker describes a fictional office scene using the words "{duty}" This is commentary, not a job requirement.',[])
                add('provider',f'You will receive introductory lessons covering how to {duty[0].lower()+duty[1:]} A dedicated trainer provides those lessons.',[])
    # Composition teaches multiple supported capabilities without inventing an
    # inferred technology. Constituent duties never cross the split boundary.
    rng=random.Random(20261014)
    for split,count in [('train',400),('dev',80)]:
        used=set()
        while len(used)<count:
            picked=rng.sample(positive[split],rng.choice([2,3]))
            if len({r[1] for r in picked})!=len(picked):
                continue
            key=tuple(sorted(r[2] for r in picked))
            if key in used:
                continue
            used.add(key)
            rows.append({'id':f'composed-{split}-{len(used)}','family':f'composed-{split}-{len(used)}',
                'component_families':list(key),'split':split,'origin':'project-authored-composition',
                'text':'Responsibilities: '+ ' '.join(r[0] for r in picked),
                'expected':[r[1] for r in picked],'acceptable':[]})
    data={'description':'Project-authored capability curriculum with explicit context contrasts and mixed-duty compositions. Not independent expert or employer labels. No previous test descriptions are copied into training.',
        'split_policy':'Nine training and three development core duties per capability. Every contextual variant stays with its core duty; composition uses only same-split duties. No test cases in this file.',
        'cases':rows}
    output.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8')
    load_cases(output)
    print(f'{len(rows)} base cases written to {output}')


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,default=Path('evaluation/context-curriculum-cases.json'))
    build(p.parse_args().output)
