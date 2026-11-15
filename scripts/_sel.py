"""Shared by the check scripts: on phones the Metric / Country / Region selectors sit in a folded <details id="sel">; open it, then select."""
def select_option(pg, selector, value):
    pg.evaluate("(()=>{const d=document.getElementById('sel');if(d)d.open=true})()")
    return pg.select_option(selector, value)
