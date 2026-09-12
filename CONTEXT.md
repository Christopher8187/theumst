# Theumst

This context defines Theumst application and deployment language. Shared
Product Workspace relationships and terms live in
`C:\Business\product\CONTEXT-MAP.md`.

Read the [shared knowledge model](../CONTEXT-MAP.md#shared-knowledge-model)
before using knowledge-object, grimoire, crystal, projection, or hierarchy
terminology.

## Vocabulary rule

Use a filesystem term, Git term, or other widely standardized technical term
whenever it describes a concept accurately. Do not replace a standard term
with a Product Workspace-specific term or keyword.

If no standard term accurately describes a genuinely unique concept, explain
the missing distinction to Christopher and ask him to settle the name and
definition before returning the task result. After Christopher settles it,
record a shared definition in `C:\Business\product\CONTEXT-MAP.md`; record a
definition used by only one repository in that repository's `CONTEXT.md`.

## Language

**Theumst**:
The application containing the public website, signed-in dashboard, Web Demo,
backend, databases, storage integrations, and deployment code.
_Avoid_: Website repository, website project

**Web Demo**:
The isolated frontend application served after the internal proxy checks the
signed-in user's access.
_Avoid_: Demo website, public website

**Tree of Wisdom**:
The sacred, tree-themed Web Demo entrance for discovering and choosing grimoires,
set apart from the study spaces reached through the realms.
_Avoid_: Arcane Library

**Book version**:
The published edition or version of a book.
_Avoid_: Processing revision

**Summon**:
Add a grimoire to a user's personal collection, which provides the reading
list underlying that user's interactive learning.

**Mind Palace**:
The collection of knowledge objects a user has checked off.

**Realm**:
A study destination entered from a grimoire, which may also reach knowledge
and learning activity across grimoires.

**Base grimoire**:
The grimoire currently displayed on the page. During exploration, it may
differ from the original grimoire from which the user departed.

**Text realm (書)**:
Follow a grimoire's sequence while studying its knowledge objects, statements,
and workings.

**Notes realm (寫)**:
Create, organize, and revisit personal attached notes and scribbles, including
notes across grimoires.

**Questions realm (問)**:
Practice the knowledge in a grimoire through exercises and problems.

**Expand realm (道)**:
Discover interesting knowledge objects outside the current book by considering
the additional prerequisite learning they require, assuming every knowledge
object in the current book has been studied.

**Review realm (覺)**:
Revisit knowledge through a spaced repetition system.

**Preview realm (天)**:
Encounter interesting, important, or cornerstone results in the current
grimoire and further grimoires reached through the Outer grimoire view.
It offers perspective and motivation by showing how much remains to learn.

**Advice realm (意)**:
Bring the advice in a book together for reflective, meditative learning.

**Progress realm (境)**:
See statistics for the current grimoire and explore the Outer grimoire view
for longer-term study planning.

**Find neighbors**:
Retrieve nearby results using the selected semantic, dependency, or
generalization closeness measure.

**Neighborhood**:
The results of Find neighbors, qualified by the selected relation as Semantic
neighborhood, Dependency neighborhood, or Generalization neighborhood.

**Attached note**:
A user's note attached to a particular knowledge object.

**Scribble**:
A personal note without a knowledge-object attachment, which may still be
associated with a book.

**COM deployment**:
The U.S. deployment at `theumst.com`, using the COM server and DigitalOcean
Spaces, with its own policies and permitted books.
_Avoid_: Production promotion, COM child

**CN deployment**:
The Chinese deployment at `theumst.cn`, using the CN server and Aliyun Object
Storage Service, with its own policies and permitted books and no synchronization
policy with the COM deployment.
_Avoid_: Production promotion, CN child

**Local deployment**:
The Windows development deployment using Docker Compose and local storage
settings.
_Avoid_: Test website, lab deployment
