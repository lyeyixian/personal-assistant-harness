// The single fixed resume template (resume spec: exactly one, no theme options).
//
// Content arrives as JSON on `sys.inputs.resume`, already display-ready: dates
// are formatted and the work-authorization line is toggled by the Python render
// step. This file owns every layout decision and invents no content.

#let doc = json(bytes(sys.inputs.resume))
#let header = doc.header

#set document(title: header.name + " - Resume", author: header.name)
#set page(paper: "a4", margin: (x: 1.5cm, y: 1.4cm))
#set text(
  font: "Libertinus Serif",
  size: 10pt,
  lang: "en",
  // Ligatures off and hyphenation off: extraction belt-and-suspenders, so an
  // ATS parser reads back exactly the words the IR carried.
  ligatures: false,
  hyphenate: false,
)
#set par(justify: false, leading: 0.58em, spacing: 0.55em)
#set list(marker: [•], indent: 0.2em, body-indent: 0.45em, spacing: 0.45em)

#let section(title, body) = {
  block(above: 0.85em, below: 0.5em, width: 100%)[
    #text(size: 9.5pt, weight: "bold", tracking: 0.06em)[#upper(title)]
    #v(-0.3em)
    #line(length: 100%, stroke: 0.5pt + luma(80))
  ]
  body
}

#let entry-head(left-body, right-body) = grid(
  columns: (1fr, auto),
  align: (left + bottom, right + bottom),
  left-body,
  text(size: 9.5pt)[#right-body],
)

#let bullet-list(items) = list(..items.map(item => [#item]))

// Header
#align(center)[
  #text(size: 18pt, weight: "bold")[#header.name]
  #v(0.3em)
  #text(size: 10.5pt)[#header.title_line]
  #v(0.35em)
  #text(size: 9pt)[#header.contact.join("  ·  ")]
  #if header.work_authorization != none [
    #v(0.3em)
    #text(size: 9pt)[#header.work_authorization]
  ]
]

#section("Summary", doc.summary)

#section(
  "Skills",
  [
    #for group in doc.skills {
      block(below: 0.35em)[*#group.category:* #group.skills.join(", ")]
    }
  ],
)

#section(
  "Experience",
  [
    #for position in doc.experience {
      block(above: 0.65em, below: 0.35em, entry-head(
        [*#position.company* — #position.title],
        position.period,
      ))
      if position.location != none {
        block(below: 0.35em, text(size: 9pt, style: "italic")[#position.location])
      }
      bullet-list(position.bullets)
    }
  ],
)

#if doc.projects.len() > 0 {
  section(
    "Projects",
    [
      #for project in doc.projects {
        block(above: 0.65em, below: 0.35em, entry-head([*#project.name*], project.link))
        bullet-list(project.bullets)
      }
    ],
  )
}

#if doc.education.len() > 0 or doc.certifications.len() > 0 {
  section(
    "Education & Certifications",
    [
      #for school in doc.education {
        block(below: 0.35em, entry-head(
          [*#school.institution* — #school.qualification],
          school.period,
        ))
      }
      #for certification in doc.certifications {
        block(below: 0.35em)[#certification]
      }
    ],
  )
}

// Read back by the render step to enforce the two-page hard cap.
#context [
  #metadata(counter(page).final().first()) <resume-page-count>
]
