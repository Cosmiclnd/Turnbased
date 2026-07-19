cdef class Item:
    cdef public:
        str nameid
        str name
        Item master
    cdef dict __dict__
    
    cpdef bint dead(self)
    cpdef void on_removed(self, ItemList list)

cdef class DeadToggle(Item):
    cdef public bool dead_toggle

    cpdef bint dead(self)

cdef class ItemList:
    cdef list items

    cpdef void refresh(self)
    cpdef void append(self, Item item)
    cpdef void extend(self, object list)
    cpdef Item pop(self, Py_ssize_t index)
    cpdef void clear(self)
    cpdef void sort(self, object key=*, bint reverse=*)
